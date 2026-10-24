? X_8001a158(s32, s32);                             /* extern */
? X_800b57fc();                                     /* extern */

void FUN_800a87f8(s32 arg1, s32 arg6, s32 arg7) {
    X_8001a158(arg1 + 0x2C, arg1 + 0xE4);
    *saved_reg_s0->unk-6568 = 0x800B57FC;
    X_800b57fc();
}
