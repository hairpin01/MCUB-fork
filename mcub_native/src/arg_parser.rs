use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySet, PyTuple};
use pyo3::{BoundObject, IntoPyObject};

#[derive(Clone)]
#[pyclass(module = "mcub_native")]
pub struct PipelineSegment {
    #[pyo3(get, set)]
    pub command: String,
    #[pyo3(get, set)]
    pub operator: Option<String>,
    #[pyo3(get, set)]
    pub exit_code: Option<i64>,
}

#[pymethods]
impl PipelineSegment {
    fn __repr__(&self) -> String {
        let op = match &self.operator {
            Some(op) => format!("'{op}'"),
            None => "None".to_string(),
        };
        let mut repr = format!("PipelineSegment(op={op}, cmd='{}'", self.command);
        if let Some(exit_code) = self.exit_code {
            repr.push_str(&format!(", exit_code={exit_code}"));
        }
        repr.push(')');
        repr
    }
}

#[pyclass(module = "mcub_native")]
pub struct ArgumentParser {
    #[pyo3(get, set)]
    pub full_text: String,
    #[pyo3(get, set)]
    pub prefix: String,
    #[pyo3(get, set)]
    pub command: String,
    #[pyo3(get, set)]
    pub raw_args: String,
    args: Py<PyList>,
    kwargs: Py<PyDict>,
    flags: Py<PySet>,
}

#[pymethods]
impl ArgumentParser {
    #[new]
    #[pyo3(signature = (text, prefix = None))]
    pub fn new(
        py: Python<'_>,
        text: &Bound<'_, PyAny>,
        prefix: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        Self::from_py(py, text, prefix)
    }

    #[getter]
    fn args(&self, py: Python<'_>) -> Py<PyList> {
        self.args.clone_ref(py)
    }

    #[setter]
    fn set_args(&mut self, value: Py<PyList>) {
        self.args = value;
    }

    #[getter]
    fn kwargs(&self, py: Python<'_>) -> Py<PyDict> {
        self.kwargs.clone_ref(py)
    }

    #[setter]
    fn set_kwargs(&mut self, value: Py<PyDict>) {
        self.kwargs = value;
    }

    #[getter]
    fn flags(&self, py: Python<'_>) -> Py<PySet> {
        self.flags.clone_ref(py)
    }

    #[setter]
    fn set_flags(&mut self, value: Py<PySet>) {
        self.flags = value;
    }

    #[pyo3(signature = (index, default = None))]
    fn get(&self, py: Python<'_>, index: isize, default: Option<Py<PyAny>>) -> PyResult<Py<PyAny>> {
        let args = self.args.bind(py);
        let len = args.len() as isize;
        let normalized = if index < 0 { len + index } else { index };
        if normalized < 0 || normalized >= len {
            return Ok(default.unwrap_or_else(|| py.None()));
        }
        Ok(args.get_item(normalized as usize)?.unbind())
    }

    fn get_flag(&self, py: Python<'_>, flag: &str) -> PyResult<bool> {
        Ok(self.flags.bind(py).contains(flag)? || self.kwargs.bind(py).contains(flag)?)
    }

    #[pyo3(signature = (key, default = None))]
    fn get_kwarg(
        &self,
        py: Python<'_>,
        key: &str,
        default: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        match self.kwargs.bind(py).get_item(key)? {
            Some(value) => Ok(value.unbind()),
            None => Ok(default.unwrap_or_else(|| py.None())),
        }
    }

    fn has(&self, py: Python<'_>, key: &str) -> PyResult<bool> {
        self.kwargs.bind(py).contains(key)
    }

    #[pyo3(signature = (start = 0, end = None))]
    fn join_args(&self, py: Python<'_>, start: isize, end: Option<isize>) -> PyResult<String> {
        let values = self.args_as_strings(py)?;
        let (start, end) = normalize_slice(start, end, values.len());
        Ok(values[start..end].join(" "))
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!(
            "ArgumentParser(command='{}', args={}, kwargs={}, flags={})",
            self.command,
            self.args.bind(py).repr()?,
            self.kwargs.bind(py).repr()?,
            self.flags.bind(py).repr()?,
        ))
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.args.bind(py).len()
    }

    fn __contains__(&self, py: Python<'_>, item: &str) -> PyResult<bool> {
        self.get_flag(py, item)
    }

    fn get_all(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        Ok(self.args.bind(py).call_method0("copy")?.unbind())
    }

    #[pyo3(signature = (start = 0, end = None))]
    fn slice(&self, py: Python<'_>, start: isize, end: Option<isize>) -> PyResult<Py<PyAny>> {
        let values = self.args_as_objects(py)?;
        let (start, end) = normalize_slice(start, end, values.len());
        let list = PyList::new(py, &values[start..end])?;
        Ok(list.into_any().unbind())
    }

    #[pyo3(signature = (*names))]
    fn require(&self, py: Python<'_>, names: &Bound<'_, PyTuple>) -> PyResult<(bool, String)> {
        for item in names.iter() {
            if let Ok(index) = item.extract::<isize>() {
                if index < 0 || index >= self.args.bind(py).len() as isize {
                    return Ok((false, format!("arg[{index}]")));
                }
                continue;
            }
            let name = stringify(&item)?;
            if !self.kwargs.bind(py).contains(name.as_str())? {
                return Ok((false, name));
            }
        }
        Ok((true, String::new()))
    }

    #[pyo3(signature = (start = 0))]
    fn remaining(&self, start: usize) -> String {
        let tokens: Vec<&str> = self.raw_args.split_whitespace().collect();
        if start >= tokens.len() {
            return String::new();
        }
        tokens[start..].join(" ")
    }
}

impl ArgumentParser {
    fn from_py(
        py: Python<'_>,
        text: &Bound<'_, PyAny>,
        prefix: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let full_text = normalize_or(text, "")?.trim().to_string();
        let prefix = match prefix {
            Some(value) if !value.is_none() => stringify(value)?,
            _ => ".".to_string(),
        };
        let mut parser = Self {
            full_text,
            prefix,
            command: String::new(),
            raw_args: String::new(),
            args: PyList::empty(py).unbind(),
            kwargs: PyDict::new(py).unbind(),
            flags: PySet::empty(py)?.unbind(),
        };
        parser.parse(py)?;
        Ok(parser)
    }

    fn parse(&mut self, py: Python<'_>) -> PyResult<()> {
        if self.full_text.is_empty() {
            return Ok(());
        }
        let Some(without_prefix) = self.full_text.strip_prefix(&self.prefix) else {
            return Err(PyValueError::new_err(format!(
                "Text doesn't start with prefix '{}'",
                self.prefix
            )));
        };
        let text_without_prefix = without_prefix.trim();
        if text_without_prefix.is_empty() {
            return Ok(());
        }
        let mut parts = text_without_prefix.splitn(2, char::is_whitespace);
        self.command = parts.next().unwrap_or_default().to_string();
        if let Some(rest) = parts.next() {
            self.raw_args = rest.trim_start().to_string();
            self.parse_arguments(py, self.raw_args.clone())?;
        }
        Ok(())
    }

    fn parse_arguments(&mut self, py: Python<'_>, args_string: String) -> PyResult<()> {
        let tokens = split_args_impl(&args_string).unwrap_or_else(|| simple_split(&args_string));
        let mut i = 0;
        while i < tokens.len() {
            let token = &tokens[i];
            if let Some(flag_name) = token.strip_prefix("--") {
                if let Some((key, value)) = flag_name.split_once('=') {
                    self.kwargs
                        .bind(py)
                        .set_item(key, parse_value(py, value)?)?;
                } else if i + 1 < tokens.len() && !tokens[i + 1].starts_with('-') {
                    self.kwargs
                        .bind(py)
                        .set_item(flag_name, parse_value(py, &tokens[i + 1])?)?;
                    i += 1;
                } else {
                    self.flags.bind(py).add(flag_name)?;
                    self.kwargs.bind(py).set_item(flag_name, true)?;
                }
            } else if let Some(flag_chars) = token.strip_prefix('-') {
                if !flag_chars.is_empty() {
                    if flag_chars.chars().count() > 1 {
                        for ch in flag_chars.chars() {
                            let flag = ch.to_string();
                            self.flags.bind(py).add(flag.as_str())?;
                            self.kwargs.bind(py).set_item(flag.as_str(), true)?;
                        }
                    } else if i + 1 < tokens.len() && !tokens[i + 1].starts_with('-') {
                        self.kwargs
                            .bind(py)
                            .set_item(flag_chars, parse_value(py, &tokens[i + 1])?)?;
                        i += 1;
                    } else {
                        self.flags.bind(py).add(flag_chars)?;
                        self.kwargs.bind(py).set_item(flag_chars, true)?;
                    }
                }
            } else {
                self.args.bind(py).append(parse_value(py, token)?)?;
            }
            i += 1;
        }
        Ok(())
    }

    fn args_as_strings(&self, py: Python<'_>) -> PyResult<Vec<String>> {
        let mut values = Vec::with_capacity(self.args.bind(py).len());
        for item in self.args.bind(py).iter() {
            values.push(item.str()?.to_str()?.to_string());
        }
        Ok(values)
    }

    fn args_as_objects(&self, py: Python<'_>) -> PyResult<Vec<Py<PyAny>>> {
        let mut values = Vec::with_capacity(self.args.bind(py).len());
        for item in self.args.bind(py).iter() {
            values.push(item.unbind());
        }
        Ok(values)
    }
}

#[derive(Clone)]
#[pyclass(module = "mcub_native")]
pub struct PipelineParser {
    #[pyo3(get, set)]
    pub text: String,
    pending_exit_code: Option<i64>,
    segments: Vec<PipelineSegment>,
}

#[pymethods]
impl PipelineParser {
    #[new]
    pub fn new(text: &Bound<'_, PyAny>) -> PyResult<Self> {
        let text = stringify(text)?;
        let mut parser = Self {
            text,
            pending_exit_code: None,
            segments: Vec::new(),
        };
        parser.segments = parser.parse();
        Ok(parser)
    }

    #[getter]
    fn segments(&self) -> Vec<PipelineSegment> {
        self.segments.clone()
    }

    #[setter]
    fn set_segments(&mut self, value: Vec<PipelineSegment>) {
        self.segments = value;
    }

    fn is_simple(&self) -> bool {
        self.segments.len() <= 1
    }

    fn __repr__(&self) -> String {
        let segments = self
            .segments
            .iter()
            .map(PipelineSegment::__repr__)
            .collect::<Vec<_>>()
            .join(", ");
        format!("PipelineParser(segments=[{segments}])")
    }
}

impl PipelineParser {
    fn parse(&mut self) -> Vec<PipelineSegment> {
        let mut segments = Vec::new();
        let chars: Vec<char> = self.text.chars().collect();
        let mut buf = String::new();
        let mut pending_op: Option<String> = None;
        let mut i = 0;
        let mut in_quotes = false;
        let mut quote_char: Option<char> = None;

        while i < chars.len() {
            let ch = chars[i];
            if ch == '\\' && !in_quotes {
                i += 1;
                if i < chars.len() {
                    let remaining: String = chars[i..].iter().collect();
                    let mut escaped = false;
                    for core in ESCAPE_CORES {
                        if remaining.starts_with(core) {
                            buf.push_str(core.trim());
                            i += core.chars().count();
                            escaped = true;
                            break;
                        }
                    }
                    if !escaped {
                        for op in ["||", "&&", "|", "&"] {
                            if remaining.starts_with(op) {
                                buf.push_str(op);
                                i += op.chars().count();
                                escaped = true;
                                break;
                            }
                        }
                    }
                    if !escaped {
                        buf.push(chars[i]);
                        i += 1;
                    }
                }
                continue;
            }

            if ch == '"' || ch == '\'' {
                if in_quotes && Some(ch) == quote_char {
                    in_quotes = false;
                    quote_char = None;
                } else if !in_quotes {
                    in_quotes = true;
                    quote_char = Some(ch);
                }
                buf.push(ch);
                i += 1;
                continue;
            }

            if in_quotes {
                buf.push(ch);
                i += 1;
                continue;
            }

            let remaining: String = chars[i..].iter().collect();
            if let Some((matched_len, matched_key)) = detect_operator(&remaining) {
                let seg = buf.trim().to_string();
                let mut exit_code = None;
                let mut advance = matched_len;

                if matched_key == "||" {
                    let after = i + advance;
                    if after < chars.len() && chars[after] == '[' {
                        if let Some(end_offset) =
                            chars[after + 1..].iter().position(|ch| *ch == ']')
                        {
                            let end_b = after + 1 + end_offset;
                            let value: String = chars[after + 1..end_b].iter().collect();
                            if let Ok(parsed) = value.parse::<i64>() {
                                exit_code = Some(parsed);
                            }
                            i = end_b + 1;
                            advance = 0;
                        }
                    }
                }

                if !seg.is_empty() {
                    segments.push(PipelineSegment {
                        command: seg,
                        operator: pending_op.clone(),
                        exit_code: self.pending_exit_code.take(),
                    });
                }
                pending_op = Some(matched_key.to_string());
                buf.clear();
                if exit_code.is_some() {
                    self.pending_exit_code = exit_code;
                }
                i += advance;
                continue;
            }

            buf.push(ch);
            i += 1;
        }

        let seg = buf.trim().to_string();
        if !seg.is_empty() {
            segments.push(PipelineSegment {
                command: seg,
                operator: pending_op,
                exit_code: self.pending_exit_code.take(),
            });
        }
        segments
    }
}

#[pyfunction]
#[pyo3(signature = (text, prefix = None))]
pub fn parse_arguments(
    py: Python<'_>,
    text: &Bound<'_, PyAny>,
    prefix: Option<&Bound<'_, PyAny>>,
) -> PyResult<ArgumentParser> {
    ArgumentParser::from_py(py, text, prefix)
}

#[pyfunction]
#[pyo3(signature = (text, prefix = None))]
pub fn extract_command(
    text: &Bound<'_, PyAny>,
    prefix: Option<&Bound<'_, PyAny>>,
) -> PyResult<(String, String)> {
    let text = stringify(text)?;
    let prefix = match prefix {
        Some(value) if !value.is_none() => stringify(value)?,
        _ => ".".to_string(),
    };
    let Some(without_prefix) = text.strip_prefix(&prefix) else {
        return Ok((String::new(), text));
    };
    let text_without_prefix = without_prefix.trim();
    if text_without_prefix.is_empty() {
        return Ok((String::new(), String::new()));
    }
    let mut parts = text_without_prefix.splitn(2, char::is_whitespace);
    let command = parts.next().unwrap_or_default().to_string();
    let args = parts.next().unwrap_or_default().to_string();
    Ok((command, args))
}

#[pyfunction]
pub fn split_args(args_string: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let normalized = normalize_or(args_string, "")?;
    Ok(split_args_impl(&normalized).unwrap_or_else(|| simple_split(&normalized)))
}

#[pyfunction]
pub fn parse_kwargs(py: Python<'_>, args_string: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let normalized = normalize_or(args_string, "")?;
    let command = format!(".cmd {normalized}");
    let text = command.into_pyobject(py).map_err(PyErr::from)?.into_any();
    let parser = ArgumentParser::from_py(py, &text, None)?;
    Ok(parser.kwargs.clone_ref(py))
}

#[pyfunction]
pub fn parse_pipeline(text: &Bound<'_, PyAny>) -> PyResult<PipelineParser> {
    PipelineParser::new(text)
}

const OPERATORS: [(&str, &str); 5] = [
    ("|> ", "|>"),
    (" || ", "||"),
    (" | ", "|"),
    (" && ", "&&"),
    ("& ", "&"),
];

const ESCAPE_CORES: [&str; 15] = [
    " |> ", "|> ", " && ", " || ", " |>", " | ", "|>", " &&", " ||", " |", "&&", "||", "|", "& ",
    "&",
];

fn detect_operator(text: &str) -> Option<(usize, &'static str)> {
    for (op_str, op_key) in OPERATORS {
        if text.starts_with(op_str) {
            return Some((op_str.chars().count(), op_key));
        }
    }
    for op in ["|>", "||", "&&"] {
        if let Some(rest) = text.strip_prefix(op) {
            let whitespace_bytes = rest
                .chars()
                .take_while(|ch| ch.is_whitespace())
                .map(char::len_utf8)
                .sum::<usize>();
            let matched = &text[..op.len() + whitespace_bytes];
            return Some((matched.chars().count(), op));
        }
    }
    None
}

fn split_args_impl(input: &str) -> Option<Vec<String>> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut chars = input.chars().peekable();
    let mut in_quotes = false;
    let mut quote_char = '\0';

    while let Some(ch) = chars.next() {
        if in_quotes {
            if ch == quote_char {
                in_quotes = false;
            } else if ch == '\\' {
                if let Some(next) = chars.next() {
                    current.push(next);
                } else {
                    current.push(ch);
                }
            } else {
                current.push(ch);
            }
            continue;
        }

        if ch == '\'' || ch == '"' {
            in_quotes = true;
            quote_char = ch;
        } else if ch.is_whitespace() {
            if !current.is_empty() {
                tokens.push(std::mem::take(&mut current));
            }
        } else if ch == '\\' {
            if let Some(next) = chars.next() {
                current.push(next);
            } else {
                current.push(ch);
            }
        } else {
            current.push(ch);
        }
    }

    if in_quotes {
        return None;
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    Some(tokens)
}

fn simple_split(input: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut in_quotes = false;
    let mut quote_char = '\0';

    for ch in input.chars() {
        if (ch == '"' || ch == '\'') && (!in_quotes || ch == quote_char) {
            if in_quotes {
                in_quotes = false;
                if !current.is_empty() {
                    tokens.push(std::mem::take(&mut current));
                }
            } else {
                in_quotes = true;
                quote_char = ch;
            }
        } else if ch == ' ' && !in_quotes {
            if !current.is_empty() {
                tokens.push(std::mem::take(&mut current));
            }
        } else {
            current.push(ch);
        }
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    tokens
}

fn parse_value(py: Python<'_>, value: &str) -> PyResult<Py<PyAny>> {
    if value.is_empty() {
        return to_py_any(py, "");
    }
    if value.chars().all(|ch| ch.is_ascii_digit()) {
        if let Ok(parsed) = value.parse::<i64>() {
            return to_py_any(py, parsed);
        }
    }
    if let Ok(parsed) = value.parse::<f64>() {
        return to_py_any(py, parsed);
    }
    match value.to_ascii_lowercase().as_str() {
        "true" | "yes" | "on" | "1" => return to_py_any(py, true),
        "false" | "no" | "off" | "0" => return to_py_any(py, false),
        _ => {}
    }
    if value.contains(',') {
        let mut parts = Vec::new();
        for part in value.split(',') {
            parts.push(parse_value(py, part.trim())?);
        }
        return Ok(PyList::new(py, &parts)?.into_any().unbind());
    }
    to_py_any(py, value.to_string())
}

fn normalize_slice(start: isize, end: Option<isize>, len: usize) -> (usize, usize) {
    let len_i = len as isize;
    let mut start_i = if start < 0 { len_i + start } else { start };
    let mut end_i = end.unwrap_or(len_i);
    if end_i < 0 {
        end_i += len_i;
    }
    start_i = start_i.clamp(0, len_i);
    end_i = end_i.clamp(0, len_i);
    if end_i < start_i {
        end_i = start_i;
    }
    (start_i as usize, end_i as usize)
}

fn normalize_or(value: &Bound<'_, PyAny>, none_value: &str) -> PyResult<String> {
    if value.is_none() {
        return Ok(none_value.to_string());
    }
    stringify(value)
}

fn stringify(value: &Bound<'_, PyAny>) -> PyResult<String> {
    Ok(value.str()?.to_str()?.to_string())
}

fn to_py_any<'py, T>(py: Python<'py>, value: T) -> PyResult<Py<PyAny>>
where
    T: IntoPyObject<'py>,
    PyErr: From<<T as IntoPyObject<'py>>::Error>,
{
    Ok(value
        .into_pyobject(py)
        .map_err(PyErr::from)?
        .into_any()
        .unbind())
}
