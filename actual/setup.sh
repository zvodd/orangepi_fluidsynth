mkdir -p /usr/local/share/soundfonts
mv FluidR3_GM.sf2 /usr/local/share/soundfonts/FluidR3_GM.sf2

mv keyboard_midi_service.py /usr/local/bin

mv keyboard-midi.service /etc/systemd/system/keyboard-midi.service


sudo systemctl daemon-reload           # Reload systemd configurations
sudo systemctl enable keyboard-midi.service # Enable to start on boot
sudo systemctl start keyboard-midi.service  # Start immediately
systemctl status keyboard-midi.service      # Check status
journalctl -u keyboard-midi.service -f   