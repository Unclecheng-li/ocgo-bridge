Option Explicit
' ============================================================================
' OpenCode Go proxy - manual start (shows a popup with the result).
'
' PORTABLE BY DESIGN
'   * No machine-specific path is hard-coded.
'   * Python interpreter: read from "python.txt" (written by install.ps1).
'     If that file is missing we fall back to "py" / "python" on PATH.
'   * Port: read from config.json (default 8787).
'   * Everything is resolved relative to the folder holding this script, so the
'     whole directory can be copied anywhere and it still works.
'
' ENCODING: ASCII only + CRLF. wscript reads .vbs as ANSI/GBK on Chinese
' Windows, so a single non-ASCII byte (e.g. a Chinese comment) corrupts the
' file and produces a confusing "expected statement" compile error.
' NEVER put Chinese text in this file.
' ============================================================================

Dim fso, ws, here, port, cands, i, ok, used

' ---- first line of python.txt, or "" --------------------------------------
Function SavedPython()
    Dim f, s
    SavedPython = ""
    If Not fso.FileExists(here & "\python.txt") Then Exit Function
    On Error Resume Next
    Set f = fso.OpenTextFile(here & "\python.txt", 1, False)
    If Err.Number <> 0 Then Err.Clear : Exit Function
    s = f.ReadLine
    f.Close
    On Error GoTo 0
    If IsNull(s) Then Exit Function
    SavedPython = Trim(s)
End Function

' ---- read "port" from config.json (crude, dependency-free) ----------------
Function CfgPort(dflt)
    Dim f, txt, p, ch, num, i
    CfgPort = dflt
    If Not fso.FileExists(here & "\config.json") Then Exit Function
    On Error Resume Next
    Set f = fso.OpenTextFile(here & "\config.json", 1, False)
    If Err.Number <> 0 Then Err.Clear : Exit Function
    txt = f.ReadAll
    f.Close
    On Error GoTo 0
    If Len(txt) = 0 Then Exit Function
    p = InStr(1, txt, """port""", vbTextCompare)
    If p = 0 Then Exit Function
    p = InStr(p, txt, ":")
    If p = 0 Then Exit Function
    num = ""
    i = p + 1
    Do While i <= Len(txt)
        ch = Mid(txt, i, 1)
        If ch >= "0" And ch <= "9" Then
            num = num & ch
        ElseIf Len(num) > 0 Then
            Exit Do
        End If
        i = i + 1
    Loop
    If Len(num) > 0 Then CfgPort = CLng(num)
End Function

' ---- is anything listening on our port? -----------------------------------
Function Listening()
    Dim s
    s = ws.Exec("cmd /c netstat -ano | findstr LISTENING | findstr :" & port).StdOut.ReadAll
    Listening = (Len(Trim(s)) > 0)
End Function

Function TryLaunch(exe)
    Dim k
    On Error Resume Next
    ws.CurrentDirectory = here
    ws.Run """" & exe & """ """ & here & "\proxy.py"" --port " & port, 0, False
    If Err.Number <> 0 Then
        Err.Clear
        TryLaunch = False
        Exit Function
    End If
    On Error GoTo 0
    For k = 1 To 10
        WScript.Sleep 700
        If Listening() Then
            TryLaunch = True
            Exit Function
        End If
    Next
    TryLaunch = False
End Function

' ============================= main ========================================
Set fso = CreateObject("Scripting.FileSystemObject")
Set ws  = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(here & "\proxy.py") Then
    ws.Popup "proxy.py not found next to this script:" & vbCrLf & here, 10, "OpenCode Go Proxy", 16
    WScript.Quit
End If

port = CfgPort(8787)

If Listening() Then
    ws.Popup "Already running on port " & port & "." & vbCrLf & _
             "http://127.0.0.1:" & port, 5, "OpenCode Go Proxy", 64
    WScript.Quit
End If

' Candidate order: what the installer saved, then portable PATH entries.
cands = Array(SavedPython(), "py", "python", "python3")

used = ""
For i = 0 To UBound(cands)
    If Len(cands(i)) > 0 Then
        ' An absolute path we can verify up front, so a stale python.txt does
        ' not cost us a full timeout. Bare names ("py"/"python") rely on PATH
        ' and can only be validated by actually trying them.
        ok = True
        If InStr(cands(i), "\") > 0 Then ok = fso.FileExists(cands(i))
        If ok Then
            If TryLaunch(cands(i)) Then
                used = cands(i)
                Exit For
            End If
        End If
    End If
Next

If used <> "" Then
    ws.Popup "Proxy started." & vbCrLf & vbCrLf & _
             "http://127.0.0.1:" & port & vbCrLf & _
             "python: " & used, 6, "OpenCode Go Proxy", 64
Else
    ws.Popup "Failed to start." & vbCrLf & vbCrLf & _
             "No working Python found, or port " & port & " is busy." & vbCrLf & _
             "Run start.bat to see the error.", 15, "OpenCode Go Proxy", 16
End If
