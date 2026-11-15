"""Daisy's complete neutral/accent theme presets."""

# Every theme is the same calm, true-black island with ONE accent, taken from the
# system colours macOS and iOS use, so each reads clearly on black and stays legible.
# Greys are Apple's dark-mode greys. Tinted surfaces get only a faint hue in the black.
# (background, surface, hover, border, accent, text, muted)
_GREYS = ('#1c1c1e', '#2c2c2e', '#38383a')
THEMES = {
    'Dark Matter': ('#000000',) + _GREYS + ('#0a84ff', '#f5f5f7', '#98989d'),   # blue
    'Graphite': ('#000000',) + _GREYS + ('#f5f5f7', '#f5f5f7', '#98989d'),      # white
    'Midnight': ('#0a0a12',) + _GREYS + ('#5e5ce6', '#f5f5f7', '#98989d'),      # indigo
    'Amethyst': ('#0e0a12',) + _GREYS + ('#bf5af2', '#f5f5f7', '#98989d'),      # purple
    'Rose': ('#120a0c',) + _GREYS + ('#ff375f', '#f5f5f7', '#98989d'),          # pink
    'Sunset': ('#120d07',) + _GREYS + ('#ff9f0a', '#f5f5f7', '#98989d'),        # orange
    'Mint': ('#08100b',) + _GREYS + ('#30d158', '#f5f5f7', '#98989d'),          # green
}


# Porcelain: the light material of notification cards, after macOS light-mode
# banners. Warm white, near-black labels, one hairline edge and a soft shadow.
PORCELAIN = dict(card='#f7f6f3', card_top='#fdfcfa', edge='#dcd9d2', highlight='#ffffff',
                 label='#1d1d1f', secondary='#6e6e73', tertiary='#8e8e93',
                 fill='#ebe9e4', fill_hover='#e1dfd9', separator='#e4e2dc', shadow='#0b0b10')
# A Dynamic Island is true black so it merges with a notch or the screen edge.
ISLAND = '#000000'


def get_theme(name='Dark Matter', surface_treatment='neutral'):
    if not isinstance(name, str) or name not in THEMES:
        name = 'Dark Matter'
    keys = ('background', 'surface', 'hover', 'border', 'accent', 'text', 'muted')
    tokens = dict(zip(keys, THEMES[name]), name=name, edge_line='#000000', danger='#ff6961')
    if surface_treatment != 'tinted':
        neutral = dict(zip(keys, THEMES['Dark Matter']))
        tokens.update({key: neutral[key] for key in keys if key != 'accent'})
    tokens['control_border'] = '#8b8b96'
    tokens.update(timer_accent='#ffb340', timer_tick='#b98b4c', timer_surface='#342410')
    # Tinted themes keep their coloured shell; neutral is a true-black island.
    tokens['island'] = tokens['background'] if surface_treatment == 'tinted' else ISLAND
    # Light each open-island page brings with it (stage_wash.py).
    tokens.update(wash_sky='#2f6299', wash_sun='#ffd27a', wash_night='#14204a')
    tokens.update({'porcelain_' + key: value for key, value in PORCELAIN.items()})
    return tokens
