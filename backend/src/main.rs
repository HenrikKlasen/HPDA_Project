use std::{
    env,
    path::{Path, PathBuf},
};

use axum::{
    Form, Json, Router,
    extract::{Query, State},
    http::StatusCode,
    routing::{get, post},
};
use polars::prelude::*;
use serde::{Deserialize, Serialize};
use tokio::fs::File;

#[derive(Serialize, Deserialize, Debug, Clone)]
struct DataFile {
    display_name: String,
    full_path: String,
}

fn read_recurse(p: &std::path::Path, res: &mut Vec<DataFile>) {
    let entries = std::fs::read_dir(p).unwrap();
    for entry in entries {
        let entry = entry.unwrap();
        if entry.metadata().unwrap().is_dir() {
            read_recurse(&entry.path(), res);
        }

        let path = entry.path();
        if path.extension() != Some("parquet".as_ref()) {
            continue;
        }

        let stem = path.file_stem().unwrap();

        res.push(DataFile {
            display_name: stem.to_string_lossy().into_owned(),
            full_path: path.to_string_lossy().into_owned(),
        });
    }
}

fn get_data_assets_folder() -> PathBuf {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        println!("Missing folder for csv files.");
    }
    let csv_folder = args.last().unwrap();
    println!("{:?}", csv_folder);

    let path = PathBuf::from(csv_folder);
    return path;
}

#[derive(Clone)]
struct ServerState {
    data_assets: PathBuf,
    data_files: Vec<DataFile>,
}

// API CALLS
async fn get_data_files(
    State(state): State<ServerState>,
) -> Result<Json<Vec<DataFile>>, StatusCode> {
    return Ok(Json(state.data_files));
}

#[derive(Deserialize)]
struct FilenameParam {
    filename: String,
}
async fn get_atribute_headers_by_filename(
    State(state): State<ServerState>,
    Query(filename): Query<FilenameParam>,
) -> Result<Json<Vec<String>>, StatusCode> {
    let file = state
        .data_files
        .iter()
        .find(|d| d.display_name == filename.filename);
    let Some(file) = file else {
        return Err(StatusCode::BAD_REQUEST);
    };

    println!("Trying to open file {}", &file.full_path);

    let mut lf =
        LazyFrame::scan_parquet(PlRefPath::new(&file.full_path), ScanArgsParquet::default())
            .unwrap();

    // Get the schema
    let schema = lf.collect_schema().unwrap();

    let mut res = Vec::<String>::new();

    for field in schema.iter_fields() {
        res.push(field.name.to_string());
    }

    return Ok(Json(res));
}

#[tokio::main]
async fn main() {
    let data_assets = get_data_assets_folder();
    tracing_subscriber::fmt::init();

    let mut data_files = Vec::<DataFile>::new();
    read_recurse(&data_assets, &mut data_files);

    let state = ServerState {
        data_assets: data_assets,
        data_files: data_files,
    };

    let app = Router::new()
        .route("/get_data_files", get(get_data_files))
        .route(
            "/get_atribute_headers_by_filename",
            get(get_atribute_headers_by_filename),
        )
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
