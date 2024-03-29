# -*- coding: utf-8 -*-
"""MusicPlayDef.s instruction set.

Attributes
----------
    mxv : int
        Maximum value of all arguments

    c_v : int
        Center value for commands PAN, BEND, and TUNE

    reverb_set : int
        SOUND_MODE_REVERB_SET (Unknown functionality)

"""
from enum import IntEnum

mxv = 0x7F
c_v = 0x40
reverb_set = 0x80


class WaitCMD(IntEnum):
    """Possible wait commands.

    Each command resets the tracks tick counter to the number specified in the
    command and acts as a break from command execution until the track counter
    reaches 0.

    """
    W00 = 0x80
    W01 = W00 + 1
    W02 = W00 + 2
    W03 = W00 + 3
    W04 = W00 + 4
    W05 = W00 + 5
    W06 = W00 + 6
    W07 = W00 + 7
    W08 = W00 + 8
    W09 = W00 + 9
    W10 = W00 + 10
    W11 = W00 + 11
    W12 = W00 + 12
    W13 = W00 + 13
    W14 = W00 + 14
    W15 = W00 + 15
    W16 = W00 + 16
    W17 = W00 + 17
    W18 = W00 + 18
    W19 = W00 + 19
    W20 = W00 + 20
    W21 = W00 + 21
    W22 = W00 + 22
    W23 = W00 + 23
    W24 = W00 + 24
    W28 = W00 + 25
    W30 = W00 + 26
    W32 = W00 + 27
    W36 = W00 + 28
    W40 = W00 + 29
    W42 = W00 + 30
    W44 = W00 + 31
    W48 = W00 + 32
    W52 = W00 + 33
    W54 = W00 + 34
    W56 = W00 + 35
    W60 = W00 + 36
    W64 = W00 + 37
    W66 = W00 + 38
    W68 = W00 + 39
    W72 = W00 + 40
    W76 = W00 + 41
    W78 = W00 + 42
    W80 = W00 + 43
    W84 = W00 + 44
    W88 = W00 + 45
    W90 = W00 + 46
    W92 = W00 + 47
    W96 = W00 + 48


class CMD(IntEnum):
    """Possible executable M4A commands.

    These commands provide the basic functionality that allows the M4A engine
    to function as a pseudo-MOD tracker.

    """
    FINE = 0xB1  # end track data
    GOTO = 0xB2  # goto cmd@address (unconditional jump)
    PATT = 0xB3  # play pattern@address
    PEND = 0xB4  # end pattern block
    REPT = 0xB5  # repeat cmd@address n times (unconditional jump)
    PREV = 0xB6  # end track data and goto previous song
    MEMACC = 0xB9  # modify song memory location
    PRIO = 0xBA  # change track priority
    TEMPO = 0xBB  # change ticks/second executed
    KEYSH = 0xBC  # modify track key-shift

    VOICE = 0xBD  # track voice
    VOL = 0xBE  # track volume
    PAN = 0xBF  # track panning
    BEND = 0xC0  # track pitch-bend (dependent on BENDR)
    BENDR = 0xC1  # track pitch-range
    LFOS = 0xC2  # LFO speed
    LFODL = 0xC3  # LFO delay
    MOD = 0xC4  # modulation depth
    MODT = 0xC5  # modulation type
    TUNE = 0xC8  # micro-tuning (c_v+<xx>)

    XCMD = 0xCD  # extension command
    xIECV = 0x08  # pseudo echo volume
    xIECL = 0x09  # pseudo echo length

    PAM = PAN


class NoteCMD(IntEnum):
    """Possible note commands.

    Each ticked note command (denoted N<xx>) creates a note under the parent
    track with an independent tick counter. However, all notes operate their
    tick counters using the global tick clock.

    Notes executed using the TIE command have an indefinite length and are
    stopped by executing EOT.

    """
    EOT = 0xCE  # End of Tie
    TIE = 0xCF
    N01 = TIE + 1
    N02 = N01 + 1
    N03 = N01 + 2
    N04 = N01 + 3
    N05 = N01 + 4
    N06 = N01 + 5
    N07 = N01 + 6
    N08 = N01 + 7
    N09 = N01 + 8
    N10 = N01 + 9
    N11 = N01 + 10
    N12 = N01 + 11
    N13 = N01 + 12
    N14 = N01 + 13
    N15 = N01 + 14
    N16 = N01 + 15
    N17 = N01 + 16
    N18 = N01 + 17
    N19 = N01 + 18
    N20 = N01 + 19
    N21 = N01 + 20
    N22 = N01 + 21
    N23 = N01 + 22
    N24 = N01 + 23
    N28 = N01 + 24
    N30 = N01 + 25
    N32 = N01 + 26
    N36 = N01 + 27
    N40 = N01 + 28
    N42 = N01 + 29
    N44 = N01 + 30
    N48 = N01 + 31
    N52 = N01 + 32
    N54 = N01 + 33
    N56 = N01 + 34
    N60 = N01 + 35
    N64 = N01 + 36
    N66 = N01 + 37
    N68 = N01 + 38
    N72 = N01 + 39
    N76 = N01 + 40
    N78 = N01 + 41
    N80 = N01 + 42
    N84 = N01 + 43
    N88 = N01 + 44
    N90 = N01 + 45
    N92 = N01 + 46
    N96 = N01 + 47


class KeyArg(IntEnum):
    """Possible MIDI key arguments for all note commands.

    The M4A engine allows for notes in the range C-2 - G8.

    """
    CnM2 = 0
    CsM2 = 1
    DnM2 = 2
    DsM2 = 3
    EnM2 = 4
    FnM2 = 5
    FsM2 = 6
    GnM2 = 7
    GsM2 = 8
    AnM2 = 9
    AsM2 = 10
    BnM2 = 11
    CnM1 = 12
    CsM1 = 13
    DnM1 = 14
    DsM1 = 15
    EnM1 = 16
    FnM1 = 17
    FsM1 = 18
    GnM1 = 19
    GsM1 = 20
    AnM1 = 21
    AsM1 = 22
    BnM1 = 23
    Cn0 = 24
    Cs0 = 25
    Dn0 = 26
    Ds0 = 27
    En0 = 28
    Fn0 = 29
    Fs0 = 30
    Gn0 = 31
    Gs0 = 32
    An0 = 33
    As0 = 34
    Bn0 = 35
    Cn1 = 36
    Cs1 = 37
    Dn1 = 38
    Ds1 = 39
    En1 = 40
    Fn1 = 41
    Fs1 = 42
    Gn1 = 43
    Gs1 = 44
    An1 = 45
    As1 = 46
    Bn1 = 47
    Cn2 = 48
    Cs2 = 49
    Dn2 = 50
    Ds2 = 51
    En2 = 52
    Fn2 = 53
    Fs2 = 54
    Gn2 = 55
    Gs2 = 56
    An2 = 57
    As2 = 58
    Bn2 = 59
    Cn3 = 60
    Cs3 = 61
    Dn3 = 62
    Ds3 = 63
    En3 = 64
    Fn3 = 65
    Fs3 = 66
    Gn3 = 67
    Gs3 = 68
    An3 = 69
    As3 = 70
    Bn3 = 71
    Cn4 = 72
    Cs4 = 73
    Dn4 = 74
    Ds4 = 75
    En4 = 76
    Fn4 = 77
    Fs4 = 78
    Gn4 = 79
    Gs4 = 80
    An4 = 81  # 440Hz
    As4 = 82
    Bn4 = 83
    Cn5 = 84
    Cs5 = 85
    Dn5 = 86
    Ds5 = 87
    En5 = 88
    Fn5 = 89
    Fs5 = 90
    Gn5 = 91
    Gs5 = 92
    An5 = 93
    As5 = 94
    Bn5 = 95
    Cn6 = 96
    Cs6 = 97
    Dn6 = 98
    Ds6 = 99
    En6 = 100
    Fn6 = 101
    Fs6 = 102
    Gn6 = 103
    Gs6 = 104
    An6 = 105
    As6 = 106
    Bn6 = 107
    Cn7 = 108
    Cs7 = 109
    Dn7 = 110
    Ds7 = 111
    En7 = 112
    Fn7 = 113
    Fs7 = 114
    Gn7 = 115
    Gs7 = 116
    An7 = 117
    As7 = 118
    Bn7 = 119
    Cn8 = 120
    Cs8 = 121
    Dn8 = 122
    Ds8 = 123
    En8 = 124
    Fn8 = 125
    Fs8 = 126
    Gn8 = 127


class VelocityArg(IntEnum):
    """Possible velocities for all note commands.

    The M4A engine supports velocities from 0 - 127.

    """
    v000 = 0
    v001 = 1
    v002 = 2
    v003 = 3
    v004 = 4
    v005 = 5
    v006 = 6
    v007 = 7
    v008 = 8
    v009 = 9
    v010 = 10
    v011 = 11
    v012 = 12
    v013 = 13
    v014 = 14
    v015 = 15
    v016 = 16
    v017 = 17
    v018 = 18
    v019 = 19
    v020 = 20
    v021 = 21
    v022 = 22
    v023 = 23
    v024 = 24
    v025 = 25
    v026 = 26
    v027 = 27
    v028 = 28
    v029 = 29
    v030 = 30
    v031 = 31
    v032 = 32
    v033 = 33
    v034 = 34
    v035 = 35
    v036 = 36
    v037 = 37
    v038 = 38
    v039 = 39
    v040 = 40
    v041 = 41
    v042 = 42
    v043 = 43
    v044 = 44
    v045 = 45
    v046 = 46
    v047 = 47
    v048 = 48
    v049 = 49
    v050 = 50
    v051 = 51
    v052 = 52
    v053 = 53
    v054 = 54
    v055 = 55
    v056 = 56
    v057 = 57
    v058 = 58
    v059 = 59
    v060 = 60
    v061 = 61
    v062 = 62
    v063 = 63
    v064 = 64
    v065 = 65
    v066 = 66
    v067 = 67
    v068 = 68
    v069 = 69
    v070 = 70
    v071 = 71
    v072 = 72
    v073 = 73
    v074 = 74
    v075 = 75
    v076 = 76
    v077 = 77
    v078 = 78
    v079 = 79
    v080 = 80
    v081 = 81
    v082 = 82
    v083 = 83
    v084 = 84
    v085 = 85
    v086 = 86
    v087 = 87
    v088 = 88
    v089 = 89
    v090 = 90
    v091 = 91
    v092 = 92
    v093 = 93
    v094 = 94
    v095 = 95
    v096 = 96
    v097 = 97
    v098 = 98
    v099 = 99
    v100 = 100
    v101 = 101
    v102 = 102
    v103 = 103
    v104 = 104
    v105 = 105
    v106 = 106
    v107 = 107
    v108 = 108
    v109 = 109
    v110 = 110
    v111 = 111
    v112 = 112
    v113 = 113
    v114 = 114
    v115 = 115
    v116 = 116
    v117 = 117
    v118 = 118
    v119 = 119
    v120 = 120
    v121 = 121
    v122 = 122
    v123 = 123
    v124 = 124
    v125 = 125
    v126 = 126
    v127 = 127


class GateArg(IntEnum):
    """Possible gates for all ticked note commands.

    Gate is an optional argument appended to the end of a ticked note command
    which adds 1-3 ticks to the note's length, allowing for finer control.

    """
    gtp1 = 1
    gtp2 = 2
    gtp3 = 3


class ModArg(IntEnum):
    """Possible arguments for the MOD command."""
    mod_vib = 0  # vibrato
    mod_tre = 1  # tremolo
    mod_pan = 2  # auto-panpot


class MemAccArg(IntEnum):
    """Possible sub-commands for the MEMACC command."""
    mem_set = 0
    mem_add = 1
    mem_sub = 2
    mem_mem_set = 3
    mem_mem_add = 4
    mem_mem_sub = 5
    mem_beq = 6
    mem_bne = 7
    mem_bhi = 8
    mem_bhs = 9
    mem_bls = 10
    mem_blo = 11
    mem_mem_beq = 12
    mem_mem_bne = 13
    mem_mem_bhi = 14
    mem_mem_bhs = 15
    mem_mem_bls = 16
    mem_mem_blo = 17


REPEATABLE = [
    CMD.VOICE, CMD.VOL, CMD.PAN, CMD.BEND, CMD.BENDR, CMD.MOD, CMD.TUNE,
    CMD.XCMD, NoteCMD.EOT
]
