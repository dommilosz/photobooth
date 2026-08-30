# Hardware test checklist

- [ ] `v4l2-ctl -d /dev/video0 --list-formats-ext` shows MJPEG 640×480 and 1920×1080
- [ ] Preview ≥ 15 FPS at 640×480
- [ ] Still capture sharp at 1080p
- [ ] Flash fires on each capture; turns off on exit
- [ ] All 4 templates: slot count matches sidecar
- [ ] Composed sheet.jpg looks correct on review screen
- [ ] CUPS print borderless on correct paper size
- [ ] Nextcloud upload: N photos + sheet.jpg in session folder
- [ ] Touch works on all screens
- [ ] Powered USB hub: camera + printer stable
