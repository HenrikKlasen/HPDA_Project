use std::{collections::HashMap, env, path::PathBuf};

use axum::{
    Json, Router,
    extract::{Query, State},
    http::StatusCode,
    routing::get,
};
use polars::lazy::prelude::*;
use polars::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Serialize, Deserialize, Debug, Clone)]
struct DataFile {
    pub display_name: String,
    pub full_path: String,
}

impl DataFile {
    pub fn get_atribute_headers(&self) -> Vec<String> {
        let mut lf =
            LazyFrame::scan_parquet(PlRefPath::new(&self.full_path), ScanArgsParquet::default())
                .unwrap();

        let schema = lf.collect_schema().unwrap();

        let mut res = Vec::<String>::new();
        for field in schema.iter_fields() {
            res.push(field.name.to_string());
        }
        res
    }
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

    let res = (*file).get_atribute_headers();
    return Ok(Json(res));
}

fn print_all_datafiles(data_files: &Vec<DataFile>) {
    for file in data_files {
        if file.display_name.starts_with("ParticipantStatusLog") {
            // Too many logs, just show one.
            if file.display_name == "ParticipantStatusLog1" {
                println!("-=-=-=-=-=-=-=-=-=-=--=-=-");
                println!("{:?}", file.display_name);
                println!("{:?}", file.get_atribute_headers())
            }
        } else {
            println!("-=-=-=-=-=-=-=-=-=-=--=-=-");
            println!("{:?}", file.display_name);
            println!("{:?}", file.get_atribute_headers());
        }
    }
}

// Returns a jsonified string of {column: name, count: u32}
async fn aggregate_fields_to_json(
    data_file: DataFile,
    column_id: String,
) -> Json<Vec<serde_json::Value>> {
    let col_id = column_id.clone();
    let df = tokio::task::spawn_blocking(move || {
        let lf = LazyFrame::scan_parquet(
            PlRefPath::new(&data_file.full_path),
            ScanArgsParquet::default(),
        )
        .unwrap();

        let res = lf
            .group_by([col(&column_id)])
            .agg([len().alias("count")])
            .collect()
            .unwrap();
        res
    })
    .await
    .unwrap();

    let keys = df.column(&col_id).unwrap().str().unwrap();
    let values = df.column("count").unwrap().u32().unwrap();

    let mut out = Vec::new();

    for (k, v) in keys.into_iter().zip(values.into_iter()) {
        if let (Some(k), Some(v)) = (k, v) {
            out.push(json!({
                "category": k,
                "count": v
            }));
        }
    }

    Json(out)
}

async fn aggregate_information(
    state: ServerState,
    file_name: &str,
    column_id: &str,
) -> Json<Vec<serde_json::Value>> {
    let data_file = state
        .data_files
        .iter()
        .find(|d| d.display_name == file_name)
        .unwrap();

    aggregate_fields_to_json(data_file.clone(), column_id.into()).await
}

async fn get_building_types(State(state): State<ServerState>) -> Json<Vec<serde_json::Value>> {
    aggregate_information(state, "Buildings", "buildingType").await
}

async fn get_check_in_types(State(state): State<ServerState>) -> Json<Vec<serde_json::Value>> {
    aggregate_information(state, "CheckinJournal", "venueType").await
}

async fn get_interest_groups(State(state): State<ServerState>) -> Json<Vec<serde_json::Value>> {
    aggregate_information(state, "Participants", "interestGroup").await
}

async fn not_implemented() -> StatusCode {
    return StatusCode::BAD_REQUEST;
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

    print_all_datafiles(&state.data_files);

    let app = Router::new()
        .route("/get_data_files", get(get_data_files))
        .route(
            "/get_atribute_headers_by_filename",
            get(get_atribute_headers_by_filename),
        )
        .route("/activity_logs", get(not_implemented))
        .route("/attributes", get(not_implemented))
        .route("/attributes/buildings/types", get(get_building_types))
        .route("/attributes/participants/interest_groups", get(get_interest_groups))
        .route("/journals", get(not_implemented))
        .route("/journals/check_in/types", get(get_check_in_types))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
