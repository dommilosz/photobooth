# Hardware test checklist

- [ ] `lsusb` shows the webcam
- [ ] `ls -l /dev/video*` exists; user is in group `video` (`groups`)
- [ ] `v4l2-ctl --list-devices` and `v4l2-ctl -d /dev/video0 --list-formats-ext` (try video1 if video0 has no formats)
- [ ] App log shows `Camera ready device=...` (config `camera.device: auto` probes all nodes)
- [ ] Preview ≥ 10 FPS at configured `preview_size`
- [ ] Still capture sharp at 1080p (or camera max)
- [ ] Flash fires on each capture; turns off on exit
- [ ] Templates: slot count matches sidecar
- [ ] Composed sheet.jpg looks correct on review screen
- [ ] CUPS print borderless on correct paper size
- [ ] Nextcloud upload: N photos + sheet.jpg in session folder
- [ ] Touch works on all screens
- [ ] Powered USB hub: camera + printer stable (especially Pi Zero)
