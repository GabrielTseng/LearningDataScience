libmonkey = shared_library(
    'monkey', # library name
    ['token.cpp', 'lexer.cpp', 'repl.cpp', 'ast.cpp', 'parser.cpp'], # source files to be compiled
    include_directories : inc, # previously declared include directories in root :code:`meson.build`
    install : true)

monkeygen = executable(
    'monkeygen',
    'main.cpp',
    include_directories : inc,
    link_with : libmonkey,
    install : true)
