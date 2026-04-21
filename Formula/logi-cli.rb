# Homebrew formula for logi-cli
# To install locally: brew install --formula ./Formula/logi-cli.rb

class LogiCli < Formula
  desc "CLI tool for Logitech Options+ device management on macOS"
  homepage "https://github.com/user/logi-pro"
  url "https://github.com/user/logi-pro/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "TODO"
  license "MIT"

  depends_on :macos
  depends_on "python@3.11"

  def install
    libexec.install "logi.py", "agent.py", "mappings.py"
    (bin/"logi").write_env_script libexec/"logi.py", PATH: "#{Formula["python@3.11"].opt_bin}:$PATH"

    bash_completion.install "completions/logi.bash" => "logi"
    zsh_completion.install "completions/logi.zsh" => "_logi"
  end

  test do
    # Agent won't be running in CI, just test --help
    assert_match "Logitech Options+", shell_output("#{bin}/logi --help")
  end
end
