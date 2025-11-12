use std::io::BufRead;
use std::sync::LazyLock;

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
        let top_k = match command {
            "TOP_10" => 10,
            "TOP_100" => 100,
            "TOP_1000" => 1000,
            "TOP_10000" => 10000,
            _ => {
                println!("Unsupported command: {}", command);
                continue;
            }
        };
        client
            .post(&query_url)
            .header("Authorization", &authorization_header)
            .header("Content-Type", "application/json")
            .json(&serde_json::json!({
                "rank_by": [ "text", "BM25", query ],
                "top_k": top_k,
            }))
            .send()
            .await?
            .error_for_status()?;
        // TODO: chech that there is at least one hit
        println!("1");
    }
    Ok(())
}
