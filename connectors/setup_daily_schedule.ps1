# Setup Daily Scheduled Task for TuffWraps Data Pull
# Run this script once as Administrator to create the scheduled task

$TaskName = "TuffWraps-Daily-Data-Pull"
$TaskPath = "E:\VS Code\Marketing Ads\connectors\daily_pull.bat"

# 8:00 AM EST daily
$Trigger = New-ScheduledTaskTrigger -Daily -At "8:00AM"

# Run whether user is logged in or not
$Action = New-ScheduledTaskAction -Execute $TaskPath -WorkingDirectory "E:\VS Code\Marketing Ads\connectors"

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

# Create the task
Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $Action -Settings $Settings -Description "Daily pull of marketing attribution data from all sources"

Write-Host ""
Write-Host "Scheduled task created: $TaskName"
Write-Host "Runs daily at 8:00 AM"
Write-Host ""
Write-Host "To test manually, run:"
Write-Host "  E:\VS Code\Marketing Ads\connectors\daily_pull.bat"
