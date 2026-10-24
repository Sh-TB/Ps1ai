? X_80019e5c(void *, ?, ?);                         /* extern */
? X_8004415c(?, void *);                            /* extern */
? X_800b179c();                                     /* extern */

void FUN_800a4588(? arg1, s32 arg8) {
    void *temp_a3;

    M2C_ERROR(/* Read from unset register $v0 */)->unkB6 = 0;
    saved_reg_s0->unk-6568->unk26 = 0xFF;
    temp_a3 = saved_reg_s0->unk-6568;
    temp_a3->unk66 = 0x100;
    temp_a3->unkA8 = 0;
    temp_a3->unk7A = (u16) (temp_a3->unk7A - 8);
    temp_a3->unk7E = (u16) (temp_a3->unk7E + 0x12);
    arg4 = temp_a3 + 0x84;
    arg5 = temp_a3 + 0xCC;
    arg6 = temp_a3 + 0x80;
    X_8004415c(arg1, temp_a3);
    X_80019e5c(saved_reg_s0->unk-6568 + 0x2C, 0x3A, 0x100);
    saved_reg_s0->unk-6568->unk0 = 0x800B179C;
    X_800b179c();
}
