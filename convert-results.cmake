# Converts results from CSV to HTML.

file(GLOB csv_files result/*.csv)
foreach (csv_file IN LISTS csv_files)
  file(RELATIVE_PATH csv_file ${CMAKE_CURRENT_SOURCE_DIR} ${csv_file})
  string(REPLACE .csv .html html_file ${csv_file})

  file(TIMESTAMP ${csv_file} csv_time)
  file(TIMESTAMP ${html_file} html_time)
  if (NOT csv_time STRGREATER html_time)
    continue()
  endif ()
  message(STATUS "Converting ${csv_file} to ${html_file}")
  execute_process(
    COMMAND php result/template.php ${csv_file} OUTPUT_FILE ${html_file})
endforeach ()
