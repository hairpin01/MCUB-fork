mod arg_parser;
mod cache;

use pyo3::prelude::*;

#[pymodule]
fn mcub_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<cache::TTLCache>()?;
    m.add_class::<arg_parser::ArgumentParser>()?;
    m.add_class::<arg_parser::PipelineParser>()?;
    m.add_class::<arg_parser::PipelineSegment>()?;
    m.add_function(wrap_pyfunction!(arg_parser::parse_arguments, m)?)?;
    m.add_function(wrap_pyfunction!(arg_parser::extract_command, m)?)?;
    m.add_function(wrap_pyfunction!(arg_parser::split_args, m)?)?;
    m.add_function(wrap_pyfunction!(arg_parser::parse_kwargs, m)?)?;
    m.add_function(wrap_pyfunction!(arg_parser::parse_pipeline, m)?)?;
    Ok(())
}
