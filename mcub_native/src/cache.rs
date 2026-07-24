use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, VecDeque};
use std::time::{SystemTime, UNIX_EPOCH};

struct CacheEntry {
    key: Py<PyAny>,
    value: Py<PyAny>,
    key_hash: isize,
    expires_at: f64,
}

#[derive(Clone, Copy, Debug)]
struct ExpiryItem {
    expires_at: f64,
    seq: u64,
    id: u64,
}

impl PartialEq for ExpiryItem {
    fn eq(&self, other: &Self) -> bool {
        self.expires_at == other.expires_at && self.seq == other.seq && self.id == other.id
    }
}

impl Eq for ExpiryItem {}

impl PartialOrd for ExpiryItem {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ExpiryItem {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse ordering: BinaryHeap pops the earliest expiry first.
        other
            .expires_at
            .partial_cmp(&self.expires_at)
            .unwrap_or(Ordering::Equal)
            .then_with(|| other.seq.cmp(&self.seq))
            .then_with(|| other.id.cmp(&self.id))
    }
}

#[pyclass(module = "mcub_native")]
pub struct TTLCache {
    #[pyo3(get, set)]
    max_size: usize,
    #[pyo3(get, set)]
    ttl: f64,
    records: HashMap<u64, CacheEntry>,
    by_hash: HashMap<isize, Vec<u64>>,
    lru: VecDeque<u64>,
    expiry_heap: BinaryHeap<ExpiryItem>,
    next_id: u64,
    heap_seq: u64,
}

#[pymethods]
impl TTLCache {
    #[new]
    #[pyo3(signature = (max_size = 1000, ttl = 300.0))]
    pub fn new(py: Python<'_>, max_size: usize, ttl: f64) -> Self {
        log_debug(py, format!("[TTLCache] init max_size={max_size} ttl={ttl}"));
        Self {
            max_size,
            ttl,
            records: HashMap::new(),
            by_hash: HashMap::new(),
            lru: VecDeque::new(),
            expiry_heap: BinaryHeap::new(),
            next_id: 1,
            heap_seq: 0,
        }
    }

    #[pyo3(signature = (key, value, ttl = None))]
    pub fn set(
        &mut self,
        py: Python<'_>,
        key: Py<PyAny>,
        value: Py<PyAny>,
        ttl: Option<f64>,
    ) -> PyResult<()> {
        let key_hash = key.bind(py).hash()?;
        let now = now_secs()?;
        let ttl_value = ttl.unwrap_or(self.ttl);
        let expires_at = now + ttl_value;

        if let Some(existing_id) = self.find_id(py, key.bind(py), key_hash)? {
            if self.is_expired(existing_id, now) {
                self.remove_id(existing_id);
            } else {
                if let Some(entry) = self.records.get_mut(&existing_id) {
                    entry.value = value;
                    entry.expires_at = expires_at;
                }
                self.touch(existing_id);
                self.push_expiry(existing_id, expires_at);
                log_debug(
                    py,
                    format!(
                        "[TTLCache] set key_hash={key_hash} ttl={ttl_value} existed=true size={} heap={}",
                        self.records.len(),
                        self.expiry_heap.len()
                    ),
                );
                self.compact_heap_if_needed();
                return Ok(());
            }
        }

        if self.max_size == 0 {
            log_debug(py, "[TTLCache] set skipped max_size=0".to_string());
            return Ok(());
        }

        if self.records.len() >= self.max_size {
            self.cleanup_expired(now);
            while self.records.len() >= self.max_size {
                let Some(evicted_id) = self.lru.pop_front() else {
                    break;
                };
                if self.records.contains_key(&evicted_id) {
                    self.remove_id(evicted_id);
                    log_debug(
                        py,
                        format!(
                            "[TTLCache] evict_lru id={evicted_id} size={} heap={}",
                            self.records.len(),
                            self.expiry_heap.len()
                        ),
                    );
                    break;
                }
            }
        }

        let id = self.next_id;
        self.next_id = self.next_id.saturating_add(1);
        self.records.insert(
            id,
            CacheEntry {
                key,
                value,
                key_hash,
                expires_at,
            },
        );
        self.by_hash.entry(key_hash).or_default().push(id);
        self.lru.push_back(id);
        self.push_expiry(id, expires_at);
        log_debug(
            py,
            format!(
                "[TTLCache] set key_hash={key_hash} ttl={ttl_value} existed=false size={} heap={}",
                self.records.len(),
                self.expiry_heap.len()
            ),
        );
        self.compact_heap_if_needed();
        Ok(())
    }

    #[pyo3(signature = (key, default = None))]
    pub fn get(
        &mut self,
        py: Python<'_>,
        key: Py<PyAny>,
        default: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let key_hash = key.bind(py).hash()?;
        let Some(id) = self.find_id(py, key.bind(py), key_hash)? else {
            log_debug(
                py,
                format!(
                    "[TTLCache] miss key_hash={key_hash} size={}",
                    self.records.len()
                ),
            );
            return Ok(default.unwrap_or_else(|| py.None()));
        };

        let now = now_secs()?;
        if self.is_expired(id, now) {
            self.remove_id(id);
            log_debug(
                py,
                format!(
                    "[TTLCache] expired key_hash={key_hash} size={}",
                    self.records.len()
                ),
            );
            return Ok(default.unwrap_or_else(|| py.None()));
        }

        self.touch(id);
        log_debug(
            py,
            format!(
                "[TTLCache] hit key_hash={key_hash} size={}",
                self.records.len()
            ),
        );
        let value = self
            .records
            .get(&id)
            .map(|entry| entry.value.clone_ref(py))
            .unwrap_or_else(|| default.unwrap_or_else(|| py.None()));
        Ok(value)
    }

    pub fn delete(&mut self, py: Python<'_>, key: Py<PyAny>) -> PyResult<()> {
        let key_hash = key.bind(py).hash()?;
        let existed = if let Some(id) = self.find_id(py, key.bind(py), key_hash)? {
            self.remove_id(id);
            true
        } else {
            false
        };
        log_debug(
            py,
            format!(
                "[TTLCache] delete key_hash={key_hash} existed={existed} size={}",
                self.records.len()
            ),
        );
        self.compact_heap_if_needed();
        Ok(())
    }

    pub fn clear(&mut self, py: Python<'_>) {
        let cache_size = self.records.len();
        let heap_size = self.expiry_heap.len();
        self.records.clear();
        self.by_hash.clear();
        self.lru.clear();
        self.expiry_heap.clear();
        log_debug(
            py,
            format!("[TTLCache] clear size={cache_size} heap={heap_size}"),
        );
    }

    pub fn size(&self) -> usize {
        self.records.len()
    }

    #[getter]
    fn _expiry_heap(&self) -> Vec<(f64, u64, u64)> {
        self.expiry_heap
            .iter()
            .map(|item| (item.expires_at, item.seq, item.id))
            .collect()
    }

    fn __len__(&self) -> usize {
        self.size()
    }
}

impl TTLCache {
    fn find_id(
        &self,
        py: Python<'_>,
        key: &Bound<'_, PyAny>,
        key_hash: isize,
    ) -> PyResult<Option<u64>> {
        let Some(ids) = self.by_hash.get(&key_hash) else {
            return Ok(None);
        };
        for id in ids {
            let Some(entry) = self.records.get(id) else {
                continue;
            };
            if entry.key.bind(py).eq(key)? {
                return Ok(Some(*id));
            }
        }
        Ok(None)
    }

    fn is_expired(&self, id: u64, now: f64) -> bool {
        self.records
            .get(&id)
            .is_some_and(|entry| entry.expires_at < now || entry.expires_at == now)
    }

    fn touch(&mut self, id: u64) {
        self.lru.retain(|candidate| *candidate != id);
        self.lru.push_back(id);
    }

    fn push_expiry(&mut self, id: u64, expires_at: f64) {
        self.heap_seq = self.heap_seq.saturating_add(1);
        self.expiry_heap.push(ExpiryItem {
            expires_at,
            seq: self.heap_seq,
            id,
        });
    }

    fn remove_id(&mut self, id: u64) {
        let Some(entry) = self.records.remove(&id) else {
            return;
        };
        let mut remove_bucket = false;
        if let Some(bucket) = self.by_hash.get_mut(&entry.key_hash) {
            bucket.retain(|candidate| *candidate != id);
            remove_bucket = bucket.is_empty();
        }
        if remove_bucket {
            self.by_hash.remove(&entry.key_hash);
        }
        self.lru.retain(|candidate| *candidate != id);
    }

    fn cleanup_expired(&mut self, now: f64) {
        while let Some(item) = self.expiry_heap.peek().copied() {
            if item.expires_at > now {
                break;
            }
            self.expiry_heap.pop();
            if self.is_expired(item.id, now) {
                self.remove_id(item.id);
            }
        }
        self.compact_heap_if_needed();
    }

    fn compact_heap_if_needed(&mut self) {
        let live_size = self.records.len();
        let heap_size = self.expiry_heap.len();
        let limit = (self.max_size * 2).max(live_size * 2).max(64);
        if heap_size <= limit {
            return;
        }

        self.expiry_heap.clear();
        let items: Vec<(u64, f64)> = self
            .records
            .iter()
            .map(|(id, entry)| (*id, entry.expires_at))
            .collect();
        for (id, expires_at) in items {
            self.push_expiry(id, expires_at);
        }
    }
}

fn now_secs() -> PyResult<f64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .map_err(|err| PyValueError::new_err(format!("system clock error: {err}")))
}

fn log_debug(py: Python<'_>, message: String) {
    let Ok(logging) = py.import("logging") else {
        return;
    };
    let Ok(logger) = logging.call_method1("getLogger", ("core.lib.time.cache",)) else {
        return;
    };
    let _ = logger.call_method1("debug", (message,));
}
