# Converts results from CSV to HTML.

find_package(Python3 COMPONENTS Interpreter)
if (NOT Python3_FOUND)
  message(WARNING "Python 3 not found. HTML files will not be generated.")
  return()
endif ()

set(stale_csvs)
file(GLOB csv_files results/*.csv)
foreach (csv_file IN LISTS csv_files)
  file(RELATIVE_PATH csv_file ${CMAKE_CURRENT_SOURCE_DIR} ${csv_file})
  string(REPLACE .csv .html html_file ${csv_file})

  file(TIMESTAMP ${csv_file} csv_time)
  file(TIMESTAMP ${html_file} html_time)
  if (NOT csv_time STRGREATER html_time)
    continue()
  endif ()

  list(APPEND stale_csvs ${csv_file})
endforeach ()

if (stale_csvs)
  message(STATUS "Converting CSV results to HTML")
  execute_process(
    COMMAND ${Python3_EXECUTABLE} results/generate_html.py ${stale_csvs}
    COMMAND_ERROR_IS_FATAL ANY
  )
endif ()
