"""Daisy's complete neutral/accent theme presets."""

# Each theme is one clear, saturated accent on true black (or on its own deep tint when the
# surface is "tinted"). The earlier set was five washed-out pastels that all read as grey.
# (background, surface, hover, border, accent, text, muted)
THEMES = {
    'Dark Matter': ('#09090b', '#111113', '#202024', '#29292d', '#8e9bff', '#f5f5f7', '#b1b1b8'),
    'Graphite': ('#131416', '#202225', '#2c2f34', '#3d424a', '#e5e5ea', '#f2f4f7', '#b4bcc6'),
    'Amethyst': ('#150d1f', '#22152f', '#2f1d42', '#45295f', '#bf5af2', '#f8f0ff', '#c2aed6'),
    'Midnight': ('#07101f', '#0e1b33', '#162846', '#223a63', '#3d9bff', '#eef5ff', '#a9bcd8'),
    'Rose': ('#1f0b12', '#32121d', '#471a2a', '#63263b', '#ff5c7c', '#fff0f4', '#dbb0bd'),
    'Mint': ('#06170f', '#0c2519', '#123424', '#1b4a33', '#30d5a0', '#effff8', '#a6cfbc'),
    'Sunset': ('#1c1104', '#2d1c08', '#40280c', '#5a3811', '#ff9f0a', '#fff7ea', '#d8bf97'),
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
