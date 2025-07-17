
### Usage

- run `alsmixer`and up the volume

- connect a usb keyboard to the opi and hit buttons

### Controls
- `1` - `+` , `q` - `\`, `a` -`'`, `z` - `/` keys are mapped to midi event keys
  Mapping is like a guitar fretboard
  Z key is E2
  A key is A2
  Q = D3
  1 = G3
- up down arrows change midi program, left and right change bank
- shift + up / down shift octave

#### todo
add volume changing.
limit bank/program select to available in soundfont.
provide link  FluidGM soundfont

Prior Art & Further Reading

- https://github.com/toyoshim/opipad
  Turn opi into a Gamepad via USB Gadget 
+ https://hyphop.github.io/mizy/
   tiny & fast embedded linux for orange pi

### keyboard ctrl-alt-del chord override
`systemctl mask ctrl-alt-del.target`


### Orange Pi Enable ADAC codec 
`/boot/armbianEnv.txt`
```
overlays=usbhost2 usbhost3 analog-codec
```


### Orange Pi Zero LTS Line Out [13 Pin Header]
![[OpiZero1_13PinHeader.png]]


### Check Audio
list audio devices: `aplay -l
speaker test
`speaker-test -t sine -f 440`
`speaker-test -D hw:0,0 -t sine -f 1000 -c 2`

adjust volume
`alsamixer`

check for midi
`amidi -l`


### Dependencies
```
apt-get fluidsynth libfluidsynth1
```

```
apt-get install python3-numpy python3-evdev
```

```
python3 -m pip install pyfluidsynth
```