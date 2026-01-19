find base_invoicing -type f \
  ! -name out \
  ! -name "*.po" \
  ! -path "base_invoicing/static/*" \
  ! -path "*/static/*" \
  \( -name "*.py" \) \
  -print0 | while IFS= read -r -d '' f; do
  {
    echo
    echo "===== FILE: $f ====="
    cat -- "$f"
  }
done > out
