use std::io::BufRead;
use std::sync::LazyLock;
use std::mem;

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

    Ok(())
}

async fn write_batch(
    batch: Vec<serde_json::Value>,
) -> Result<(), anyhow::Error> {
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
                    "full_text_search": true,
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
