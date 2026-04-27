# Reloads Machine + User PATH from the registry into the current process.
# Use after installing software (e.g. Docker Desktop) so `docker` is found
# without closing the terminal.
$machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
$user = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machine;$user"
