Option Explicit
Dim shell, files, folder, python, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
python = folder & "\.venv\Scripts\pythonw.exe"
If Not files.FileExists(python) Then
  python = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\anaconda3\pythonw.exe"
End If
If Not files.FileExists(python) Then
  MsgBox "Python runtime not found. Contact the local administrator.", 16, "Insurance Intelligence"
  WScript.Quit 1
End If
shell.CurrentDirectory = folder
command = Chr(34) & python & Chr(34) & " " & Chr(34) & folder & "\launcher.py" & Chr(34)
shell.Run command, 0, False
