class BankInstrumentCycler:
    def __init__(self, slots):
        if not isinstance(slots, list) or not slots:
            raise ValueError("slots must be a non-empty list.")
        if not all(isinstance(t, tuple) and len(t) == 2 and all(isinstance(x, int) for x in t) for t in slots):
            raise ValueError("Each slot must be a tuple of two integers.")

        self._banks = sorted({bank for bank, _ in slots})
        self._instruments_by_bank = {}
        for bank, instr in sorted(slots):
            self._instruments_by_bank.setdefault(bank, set()).add(instr)
        self._instruments_by_bank = {k: sorted(v) for k, v in self._instruments_by_bank.items()}

        self._current_bank_idx = 0
        self._current_instrument_idx = 0
        self._align_instrument_index()

    def _align_instrument_index(self):
        instruments = self._instruments_by_bank.get(self.get_current_bank(), [])
        if self._current_instrument_idx >= len(instruments):
            self._current_instrument_idx = 0

    def get_current_bank(self):
        return self._banks[self._current_bank_idx] if self._banks else None

    def get_current_instrument(self):
        bank = self.get_current_bank()
        instruments = self._instruments_by_bank.get(bank, [])
        return instruments[self._current_instrument_idx] if instruments else None

    def get_current_bank_instrument(self):
        bank, instr = self.get_current_bank(), self.get_current_instrument()
        return [bank, instr] if bank is not None and instr is not None else []

    def change_bank(self, direction):
        if not self._banks: return []
        self._current_bank_idx = (self._current_bank_idx + direction) % len(self._banks)
        self._align_instrument_index()
        return self.get_current_bank_instrument()

    def change_instrument(self, direction):
        instruments = self._instruments_by_bank.get(self.get_current_bank(), [])
        if not instruments: return []
        self._current_instrument_idx = (self._current_instrument_idx + direction) % len(instruments)
        return self.get_current_bank_instrument()



def test_banking(available_slots_data=None):
    if available_slots_data is None:
        available_slots_data = [
            (0, 10), (0, 20), (0, 30),
            (1, 10), (1, 20), (1, 30),
            (2, 5), (2, 15),
            (3, 40), (3, 50), (3, 60), (3, 70)
        ]

    cycler = BankInstrumentCycler(available_slots_data)

    print(f"Initial selection: {cycler.get_current_bank_instrument()}")
    # Expected: [1, 10]

    print("\n--- Changing Instrument ---")
    print(f"Instrument up: {cycler.change_instrument(1)}") # [1, 20]
    print(f"Instrument up: {cycler.change_instrument(1)}") # [1, 30]
    print(f"Instrument up (wrap): {cycler.change_instrument(1)}") # [1, 10]
    print(f"Instrument down: {cycler.change_instrument(-1)}") # [1, 30]

    print("\n--- Changing Bank ---")
    print(f"Change bank up: {cycler.change_bank(1)}") # [2, 5] (instrument resets to first in new bank)
    print(f"Current selection after bank change: {cycler.get_current_bank_instrument()}")

    print("\n--- Changing Instrument in New Bank ---")
    print(f"Instrument up: {cycler.change_instrument(1)}") # [2, 15]
    print(f"Instrument up (wrap): {cycler.change_instrument(1)}") # [2, 5]

    print("\n--- Changing Bank Again ---")
    print(f"Change bank up: {cycler.change_bank(1)}") # [3, 40] (instrument resets to first in new bank)
    print(f"Change bank up (wrap): {cycler.change_bank(1)}") # [1, 10] (instrument resets to first in new bank)
    print(f"Change bank down: {cycler.change_bank(-1)}") # [3, 40]

    # print("\n--- Edge Case: Single Slot ---")
    # single_slot_data = [(99, 999)]
    # single_cycler = BankInstrumentCycler(single_slot_data)
    # print(f"Initial: {single_cycler.get_current_bank_instrument()}") # [99, 999]
    # print(f"Bank up: {single_cycler.change_bank(1)}") # [99, 999] (wraps)
    # print(f"Instrument up: {single_cycler.change_instrument(1)}") # [99, 999] (wraps)

    print("\n--- Error Handling ---")
    try:
        BankInstrumentCycler([])
    except ValueError as e:
        print(f"Caught expected error: {e}")

    try:
        BankInstrumentCycler([(1, 10), (2, "invalid")])
    except ValueError as e:
        print(f"Caught expected error: {e}")



if __name__ == "__main__":
    import sdl3
    sdl3.SDL_Init(sdl3.SDL_INIT_AUDIO)
    import fluidsynth


    def list_instruments(synth, sfid):
        """List all instruments (presets) in a SoundFont."""
        instruments = []
        sfont = fluidsynth.fluid_synth_get_sfont_by_id(synth.synth, sfid)
        if not sfont:
            return instruments

        for bank in range(128):  # Iterate through possible banks
            for preset in range(128):  # Iterate through possible presets
                preset_ptr = fluidsynth.fluid_sfont_get_preset(sfont, bank, preset)
                if preset_ptr:
                    name = fluidsynth.fluid_preset_get_name(preset_ptr).decode('ascii')
                    instruments.append((bank, preset, name))
        return instruments

    fs = fluidsynth.Synth(gain=1.0)
    
    fs.start(driver="sdl3")
    sfid = fs.sfload("E:/MUSIC/SoundsFonts/FluidR3_GM.sf2")
    inst_list = list_instruments(fs, sfid)

    lastbank = None
    inst_list.sort(key=lambda x: (x[0], x[1]))  # Sort by bank and preset number
    for bank, preset, name in inst_list:
        if bank != lastbank:
            print(f"\nBank {bank}:")
            lastbank = bank
        print(f"Preset: {preset}, Name: {name}")

    inst_list_tuple = [(bank, preset) for bank, preset, _ in inst_list]
    # BankInstrumentCycler(available_slots_data = inst_list)
    test_banking(inst_list_tuple)