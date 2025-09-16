This is an example of the commands that had to be executed to run this
benchmark on a fresh new machine running Amazon Linux 2023.

First install some packages:
```
sudo yum install git make gcc gcc-c++ docker
sudo usermod -a -G docker ec2-user
```

At this point you need to log off and on again for the group change to be
effective.

```
sudo systemctl start docker
```

Then install Rust and Java.

```
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
. "$HOME/.cargo/env"

wget https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.8_9.tar.gz
tar -xvzf OpenJDK21U-jdk_x64_linux_hotspot_21.0.8_9.tar.gz
export JAVA_HOME="$PWD/jdk-21.0.8+9/"
export PATH="$PATH:$PWD/jdk-21.0.8+9/bin"
```

All dependencies are installed, we can check out the benchmark and run it.

```
git clone --recurse-submodules git@github.com:quickwit-oss/search-benchmark-game.git
cd search-benchmark-game
```

At this point you may want to edit the Makefile to customize tasks that need to run and

```
make corpus
make compile
make index
make bench
```

You're done, make sure to note the Java / Rust / kernel versions and copy the
results.json file on another machine before shutting this one down.

