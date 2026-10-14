Option Explicit
' ============================================================================
' OpenCode Go proxy - SILENT autostart.
'
' This file is generated/copied by install.ps1 into the user's Startup folder.
' It must locate proxy.py WITHOUT relying on its own location, because in the
' Startup folder it sits next to nothing. install.ps1 therefore writes the real
' proxy directory into proxy_dir.txt, and we read it from there.
'
' Lookup order for the proxy directory:
'   1) proxy_dir.txt next to this script  (written by install.ps1)
'   2) OPENCODEGO_PROXY_HOME environment variable
'   3) a folder named OpenCodeGoProxy found under the user profile
'
' ENCODING: ASCII only + CRLF (wscript reads .vbs as ANSI/GBK on Chinese
' Windows). NEVER put Chinese text in this file.
' ============================================================================

Dim fso, ws, here, home, port, cands, i, ok, used

Function ReadFirstLine(path)
    Dim f, s
    ReadFirstLine = ""
    If Not fso.FileExists(path) Then Exit Function
    On Error Resume Next
    Set f = fso.OpenTextFile(path, 1, False)
    If Err.Number <> 0 Then Err.Clear : Exit Function
    s = f.ReadLine
    f.Close
    On Error GoTo 0
    If IsNull(s) Then Exit Function
    ReadFirstLine = Trim(s)
End Function

' ---- locate the real proxy directory --------------------------------------
Function FindHome()
    Dim envv, base, sub_
    FindHome = ""

    ' 1) proxy_dir.txt written by the installer
    FindHome = ReadFirstLine(here & "\proxy_dir.txt")
    If Len(FindHome) > 0 Then
        If fso.FileExists(FindHome & "\proxy.py") Then Exit Function
        FindHome = ""
    End If

    ' 2) environment variable
    envv = ws.ExpandEnvironmentStrings("%OPENCODEGO_PROXY_HOME%")
    If envv <> "%OPENCODEGO_PROXY_HOME%" And Len(envv) > 0 Then
        If fso.FileExists(envv & "\proxy.py") Then
            FindHome = envv
            Exit Function
        End If
    End If

    ' 3) well-known locations under the user profile
    base = ws.ExpandEnvironmentStrings("%USERPROFILE%")
    If fso.FolderExists(base) Then
        If fso.FolderExists(base & "\OpenCodeGoProxy") Then
            If fso.FileExists(base & "\OpenCodeGoProxy\proxy.py") Then
                FindHome = base & "\OpenCodeGoProxy"
                Exit Function
            End If
        End If
        If fso.FolderExists(base & "\Desktop\OpenCodeGoProxy") Then
            If fso.FileExists(base & "\Desktop\OpenCodeGoProxy\proxy.py") Then
                FindHome = base & "\Desktop\OpenCodeGoProxy"
                Exit Function
            End If
        End If
    End If

    FindHome = ""
End Function

Function CfgPort(dflt)
    Dim f, txt, p, ch, num, i
    CfgPort = dflt
    If Not fso.FileExists(home & "\config.json") Then Exit Function
    On Error Resume Next
    Set f = fso.OpenTextFile(home & "\config.json", 1, False)
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

Function Listening()
    Dim s
    s = ws.Exec("cmd /c netstat -ano | findstr LISTENING | findstr :" & port).StdOut.ReadAll
    Listening = (Len(Trim(s)) > 0)
End Function

Function TryLaunch(exe)
    Dim k
    On Error Resume Next
    ws.CurrentDirectory = home
    ws.Run """" & exe & """ """ & home & "\proxy.py"" --port " & port, 0, False
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

home = FindHome()
If Len(home) = 0 Then WScript.Quit          ' nothing we can do, stay silent

port = CfgPort(8787)
If Listening() Then WScript.Quit            ' already up

cands = Array(ReadFirstLine(home & "\python.txt"), "py", "python", "python3")

used = ""
For i = 0 To UBound(cands)
    If Len(cands(i)) > 0 Then
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
