import fluidsynth

fs = fluidsynth.Synth(gain=1.0)
fs.start(driver="alsa")

# Load a SoundFont (.sf2 file)
sfid = fs.sfload("/usr/local/share/soundfonts/FluidR3_GM.sf2")

print(f"SoundFont loaded with ID: {sfid}")

# This returns a generator of preset objects (fluid_preset_t)
soundfont = fs.sfont(sfid)
for preset in soundfont.presets():
    print(f"Bank: {preset.bank}, Program: {preset.num}, Name: {preset.name}")