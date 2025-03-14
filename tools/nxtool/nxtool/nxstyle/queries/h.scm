; check include guard
((preproc_ifdef
  "#ifndef"
  .
  name: (identifier) @guard.ifdef
  .
  (preproc_def name: (identifier) @guard.define)
  .
  (_)*
  .
  "#endif")
  .
 (comment) @guard.endif)