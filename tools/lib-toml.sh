# Adapted from wolffe-lang/scent ea1b5b19 tools/lib-toml.sh; own code.
# lib-toml.sh: sourced, never run. Reads one value from wolf-toolchain.toml.
#
# toml_value SECTION KEY prints the value with its quotes removed, or
# nothing. The pin file is a flat TOML file of quoted strings, which is all
# this reads.
toml_value() {
    awk -v s="[$1]" -v k="$2" '
        $0 == s { in_s = 1; next }
        /^\[/ { in_s = 0 }
        in_s && $1 == k {
            sub(/^[^=]*= */, "")
            gsub(/"/, "")
            print
            exit
        }
    ' "${ALPHA_ROOT:-.}/wolf-toolchain.toml"
}

# host_target prints the release archive's target triple for this machine.
host_target() {
    case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) echo aarch64-apple-darwin ;;
    Linux-x86_64) echo x86_64-unknown-linux-gnu ;;
    Linux-aarch64 | Linux-arm64) echo aarch64-unknown-linux-gnu ;;
    *) return 1 ;;
    esac
}
