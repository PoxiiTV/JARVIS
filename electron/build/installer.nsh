; Al desinstalar, ofrecer borrar tambien los datos de usuario.
;
; Sin esto quedarian ~3 GB huerfanos en %APPDATA%\J.A.R.V.I.S (los entornos
; de Python). Se pregunta en vez de borrar sin avisar: ahi tambien estan las
; claves y la voz de referencia del usuario.
!macro customUnInstall
  ${ifNot} ${isUpdated}
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "¿Borrar también tus datos?$\r$\n$\r$\n\
Se eliminarán los entornos de Python (unos 3 GB), tus claves y la voz de referencia.$\r$\n$\r$\n\
Elige No si vas a reinstalar J.A.R.V.I.S. más adelante." \
      /SD IDNO IDNO saltarDatos
    RMDir /r "$APPDATA\J.A.R.V.I.S"
    saltarDatos:
  ${endIf}
!macroend
