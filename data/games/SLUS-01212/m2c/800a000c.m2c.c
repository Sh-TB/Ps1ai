? X_800196a4(void *, void *, s16, s16);             /* extern */
s32 X_800279a0(?);                                  /* extern */

void FUN_800a000c(void *arg1, s32 arg10, s32 arg11) {
    arg4 = (s32) arg1->unk1C;
    arg5 = (s32) arg1->unk2A;
    arg6 = (s32) arg1->unk1E;
    arg7 = arg1->unk27 | (arg1->unk28 << 8);
    X_800196a4(arg1 + 0x30, arg1 + 0x78, arg1->unk18, arg1->unk1A);
    if (X_800279a0(0x800B7E84) != 0) {
        *saved_reg_s0->unk-6568 = 0x800151DC;
    }
}
