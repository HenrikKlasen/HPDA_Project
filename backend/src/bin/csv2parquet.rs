use polars::lazy::prelude::*;
use polars::prelude::*;
use std::env;
use std::path::{Path, PathBuf};

fn polars_parquet_transform(file_path: PathBuf, new_path: PathBuf) {
    let f1 = file_path.to_str().unwrap();
    let f2 = new_path.to_str().unwrap();

    let lf = LazyCsvReader::new(PlRefPath::new(f1))
        .with_has_header(true)
        .with_infer_schema_length(Some(1000))
        // A first try failed because a column had a `NA` do denote `no value`. this is not Nashville.
        .with_null_values(Some(NullValues::AllColumnsSingle(PlSmallStr::from_str(
            "NA",
        ))))
        .finish()
        .unwrap()
        .with_new_streaming(true);

    let sync_type = SinkDestination::File {
        target: SinkTarget::Path(PlRefPath::new(f2)),
    };

    lf.sink(
        sync_type,
        FileWriteFormat::Parquet(Default::default()),
        UnifiedSinkArgs::default(),
    )
    .unwrap()
    .collect()
    .unwrap();
}

fn read_recurse(p: &std::path::Path) {
    let entries = std::fs::read_dir(p).unwrap();
    for entry in entries {
        let entry = entry.unwrap();
        if entry.metadata().unwrap().is_dir() {
            read_recurse(&entry.path());
        }

        let path = entry.path();
        let new_path = path.with_extension("parquet");
        if new_path.exists() {
            continue;
        }

        if path.extension() != Some("csv".as_ref()) {
            continue;
        }

        let filename = entry.file_name().into_string().unwrap();
        if !filename.ends_with("csv") {
            continue;
        }

        polars_parquet_transform(path, new_path);
    }
}

fn main() -> PolarsResult<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        println!("Missing folder for csv files.");
    }
    let csv_folder = args.last().unwrap();
    println!("{:?}", csv_folder);

    let path = Path::new(csv_folder);
    read_recurse(path);

    println!("Successfully converted 16GB CSV to compressed Parquet.");
    Ok(())
}
