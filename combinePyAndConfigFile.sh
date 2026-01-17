for file in pi_cam_service_py311/*.{json,py}; do
  [ -e "$file" ] || continue   # Skip if no matching files
  echo -e "===== $file =====\n"
  cat "$file"
done > combined_files.txt

