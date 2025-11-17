use std::io::BufRead;
use std::sync::LazyLock;

use serde::Deserialize;

const API_URL: &str = "http://localhost:3001";
const API_KEY: LazyLock<String> = LazyLock::new(|| {
    std::env::var("TURBOPUFFER_API_KEY").expect("TURBOPUFFER_API_KEY must be set")
});

const NAMESPACE: &str = "search-benchmark-game";

#[tokio::main]
async fn main() -> Result<(), anyhow::Error> {
    let client = reqwest::Client::new();
    let query_url = format!("{API_URL}/v2/namespaces/{NAMESPACE}/query");
    let authorization_header = format!("Bearer {}", API_KEY.as_str());
    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = line?;
        let fields: Vec<&str> = line.split("\t").collect();
        assert_eq!(
            fields.len(),
            2,
            "Expected a line in the format <COMMAND> query."
        );
        let command = fields[0];
        let query = fields[1];
        let (top_k, filter) = match command {
            "TOP_10" => (10, None),
            "TOP_100" => (100, None),
            "TOP_1000" => (1000, None),
            "TOP_10000" => (10000, None),
            "TOP_10_FILTER_80%" => (10, Some("80%")),
            "TOP_10_FILTER_20%" => (10, Some("20%")),
            "TOP_10_FILTER_5%" => (10, Some("5%")),
            "TOP_100_FILTER_80%" => (100, Some("80%")),
            "TOP_100_FILTER_20%" => (100, Some("20%")),
            "TOP_100_FILTER_5%" => (100, Some("5%")),
            "TOP_1000_FILTER_80%" => (1000, Some("80%")),
            "TOP_1000_FILTER_20%" => (1000, Some("20%")),
            "TOP_1000_FILTER_5%" => (1000, Some("5%")),
            _ => {
                println!("Unsupported command: {}", command);
                continue;
            }
        };
        let body = match filter {
            Some(filter) => serde_json::json!({
                "rank_by": [ "text", "BM25", query ],
                "filters": [ "filter", "Contains", filter],
                "top_k": top_k,
                "consistency": {"level": "eventual"},
            }),
            None => serde_json::json!({
                "rank_by": [ "text", "BM25", query ],
                "top_k": top_k,
                "consistency": {"level": "eventual"},
            }),
        };
        let response = client
            .post(&query_url)
            .header("Authorization", &authorization_header)
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await?
            .error_for_status()?
            .json::<QueryResponse>()
            .await?;

        // Ensure the entire data set is indexed.
        assert_eq!(response.performance.exhaustive_search_count, 0);

        println!("{}", response.rows.len());
    }
    Ok(())
}

#[derive(Deserialize)]
struct QueryResponse {
    rows: Vec<Row>,
    performance: QueryPerformance,
}

#[derive(Deserialize)]
struct Row {}

#[derive(Deserialize)]
struct QueryPerformance {
    exhaustive_search_count: u64,
}
