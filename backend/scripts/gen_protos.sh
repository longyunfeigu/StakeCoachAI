#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
proto_dir="$root_dir/grpc_app/protos"
out_dir="$root_dir/grpc_app/generated"

mkdir -p "$out_dir"

# Prefer python3 explicitly; fallback to python
PY_BIN="python3"
command -v python3 >/dev/null 2>&1 || PY_BIN="python"

"$PY_BIN" -m grpc_tools.protoc \
  -I"$proto_dir" \
  --python_out="$out_dir" \
  --grpc_python_out="$out_dir" \
  $(find "$proto_dir" -name "*.proto" -print)

# Post-process precisely: in each *_pb2_grpc.py, make only its sibling *_pb2 import relative.
# Example in user_pb2_grpc.py: from forge.v1 import user_pb2 as x  ->  from . import user_pb2 as x
fix_count=0
while IFS= read -r -d '' file; do
  base="$(basename "$file")"
  pb2_mod="${base%_grpc.py}"  # e.g., user_pb2
  # Replace only the line importing this pb2 module (leave google.protobuf imports intact)
  if sed -n "/^from[[:space:]][A-Za-z0-9_.]\+[[:space:]]\+import[[:space:]]\+${pb2_mod}[[:space:]]\+as/p" "$file" >/dev/null; then
    sed -i -E "s#^from[[:space:]]+[A-Za-z0-9_.]+[[:space:]]+import[[:space:]]+${pb2_mod}[[:space:]]+as#from . import ${pb2_mod} as#" "$file"
    fix_count=$((fix_count+1))
  fi
done < <(find "$out_dir" -type f -name "*_pb2_grpc.py" -print0)

echo "Protos generated to $out_dir (fixed imports: $fix_count files)"
