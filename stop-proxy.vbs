Option Explicit
' ============================================================================
' OpenCode Go proxy - stop the running instance.
'
' Reads the port from config.json and kills whatever is listening on it.
' Path-independent: only needs config.json next to this script.
'
' ENCODING: ASCII only + CRLF. NEVER put Chinese text in this file.
' ============================================================================

Dim fso, ws, here, port, o, lines, line, parts, k, pid, killed

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

Function LastToken(s)
    Dim t, i
    t = Split(Trim(s))
    LastToken = ""
    For i = UBound(t) To 0 Step -1
        If Len(Trim(t(i))) > 0 Then
            LastToken = Trim(t(i))
            Exit Function
        End If
    Next
End Function

Set fso = CreateObject("Scripting.FileSystemObject")
Set ws  = CreateObject("WScript.Shell")

here = fso.GetParentFolderName(WScript.ScriptFullName)
port = CfgPort(8787)

o = ws.Exec("cmd /c netstat -ano | findstr LISTENING | findstr :" & port).StdOut.ReadAll

If Len(Trim(o)) = 0 Then
    ws.Popup "Proxy is not running (port " & port & ").", 5, "OpenCode Go Proxy", 64
    WScript.Quit
End If

killed = 0
lines = Split(o, vbCrLf)
For k = 0 To UBound(lines)
    line = Trim(lines(k))
    If Len(line) > 0 Then
        pid = LastToken(line)
        If IsNumeric(pid) And pid <> "0" Then
            ws.Exec "taskkill /PID " & pid & " /F"
            killed = killed + 1
        End If
    End If
Next

If killed > 0 Then
    ws.Popup "Stopped " & killed & " process(es) on port " & port & "." & vbCrLf & _
             "Start it again before using OpenCode Go.", 6, "OpenCode Go Proxy", 64
Else
    ws.Popup "Nothing to stop.", 5, "OpenCode Go Proxy", 64
End If
