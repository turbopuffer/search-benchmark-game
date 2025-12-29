use std::io::BufRead;
use std::mem;
use std::sync::LazyLock;
use std::time::Duration;

use serde::Deserialize;
use tokio::task::JoinSet;

const API_URL: &str = "http://localhost:3001";
const API_KEY: LazyLock<String> = LazyLock::new(|| {
    std::env::var("TURBOPUFFER_API_KEY").expect("TURBOPUFFER_API_KEY must be set")
});

const NAMESPACE: &str = "search-benchmark-game";
const BATCH_SIZE: usize = 10_000;
const MAX_CONCURRENCY: usize = 32;

#[tokio::main]
async fn main() -> Result<(), anyhow::Error> {
    env_logger::init();

    if let Ok(_) = delete_namespace().await {
        println!("namespace {NAMESPACE} deleted");
    } else {
        println!("namespace {NAMESPACE} not found, ignoring");
    }

    let mut join_set = JoinSet::new();
    let mut i = 0;
    let mut batch = vec![];

    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        i += 1;
        if i % 100_000 == 0 {
            println!("{}", i);
        }
        let doc = serde_json::from_str(&line)?;
        batch.push(doc);
        if batch.len() >= BATCH_SIZE {
            join_set.spawn(write_batch(mem::take(&mut batch)));
        }
        if join_set.len() >= MAX_CONCURRENCY {
            let _ = join_set.join_next().await.unwrap()?;
        }
    }

    for result in join_set.join_all().await {
        result?;
    }

    wait_for_index().await?;

    Ok(())
}

async fn delete_namespace() -> Result<(), anyhow::Error> {
    let client = reqwest::Client::new();
    client
        .delete(format!("{API_URL}/v1/namespaces/{NAMESPACE}"))
        .header("Authorization", format!("Bearer {}", API_KEY.as_str()))
        .send()
        .await?
        .error_for_status()?;
    println!("namespace deleted");
    Ok(())
}

async fn write_batch(batch: Vec<serde_json::Value>) -> Result<(), anyhow::Error> {
    let client = reqwest::Client::new();
    client
        .post(format!("{API_URL}/v2/namespaces/{NAMESPACE}"))
        .header("Authorization", format!("Bearer {}", API_KEY.as_str()))
        .json(&serde_json::json!({
            "upsert_rows": batch,
            "schema": {
                "id": "string",
                "text": {
                    "type": "string",
                    "full_text_search": {
                        "remove_stopwords": false,
                        "k1": 0.9,
                        "b": 0.4,
                    }
                },
                "filter": {
                    "type": "[]string",
                }
            },
            "disable_backpressure": true,
        }))
        .send()
        .await?
        .error_for_status()?;
    println!("batch written");
    Ok(())
}

async fn wait_for_index() -> Result<(), anyhow::Error> {
    #[derive(Deserialize)]
    struct MetadataResponse {
        index: IndexStatus,
    }

    #[derive(Deserialize)]
    struct IndexStatus {
        status: String,
        unindexed_bytes: Option<usize>,
    }

    loop {
        let client = reqwest::Client::new();
        let response = client
            .get(format!("{API_URL}/v1/namespaces/{NAMESPACE}/metadata"))
            .header("Authorization", format!("Bearer {}", API_KEY.as_str()))
            .send()
            .await?
            .error_for_status()?
            .json::<MetadataResponse>()
            .await?;
        if response.index.status == "up-to-date" {
            println!("index up-to-date");
            return Ok(());
        } else {
            println!(
                "index not up-to-date; unindexed bytes: {}",
                response.index.unindexed_bytes.unwrap()
            );
        }
        tokio::time::sleep(Duration::from_secs(10)).await;
    }
}
