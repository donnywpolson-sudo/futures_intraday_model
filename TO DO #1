# Keep PC awake + network alive
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 30
powercfg -h off

# Prevent network adapter power-down
Get-NetAdapter | ForEach-Object {
  powercfg /devicequery wake_armed | Out-Null
  $name = $_.Name
  Get-CimInstance MSPower_DeviceEnable -Namespace root/wmi |
    Where-Object { $_.InstanceName -like "*$($name.Replace('\','\\'))*" } |
    ForEach-Object { $_.Enable = $false; Set-CimInstance $_ }
}

# Restart Codex CLI / verify login
codex --version
codex
