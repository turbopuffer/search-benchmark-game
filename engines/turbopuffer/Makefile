clean:
	rm -fr idx
	rm -fr target

compile: target/release/build_index target/release/do_query

index:
	@echo "\n\n\n---- Indexing turbopuffer ----"
	export RUST_LOG=info && target/release/build_index < ${CORPUS}

serve: target/release/do_query
	@target/release/do_query idx

target/release/%: src/bin/%.rs
	@echo "\n\n\n--- Building turbopuffer's binary ---"
	@RUSTFLAGS='-C target-cpu=native' cargo build --release --bin $(notdir $@)
