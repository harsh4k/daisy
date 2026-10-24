"""Daisy's complete neutral/accent theme presets."""

THEMES = {
    'Dark Matter': ('#09090b', '#111113', '#202024', '#29292d', '#c1b7d4', '#f5f5f7', '#b1b1b8'),
    'Graphite': ('#131416', '#202225', '#2c2f34', '#3d424a', '#b5c5d9', '#f2f4f7', '#b4bcc6'),
    'Amethyst': ('#191121', '#291c36', '#39284a', '#503763', '#d1a6f4', '#faf2ff', '#c5b0d4'),
    'Midnight': ('#0e1523', '#17243a', '#23334e', '#344969', '#9abff7', '#eff5ff', '#afc0d9'),
    'Rose': ('#201319', '#321e28', '#472c3a', '#614051', '#efb0c8', '#fff1f6', '#d4b5c2'),
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
