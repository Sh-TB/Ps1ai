s32 X_800af1b0();                                   /* extern */
? X_800b13a0();                                     /* extern */
? X_800b1a4c();                                     /* extern */

void FUN_800a41d8(s32 arg4, s32 arg5) {
    if (saved_reg_s0->unk-6568->unk28 & 0x80) {
        X_800b1a4c();
        X_800b13a0();
        return;
    }
    if (X_800af1b0() != 0) {
        saved_reg_s0->unk-6568->unk0 = 0x800151DC;
    }
}
