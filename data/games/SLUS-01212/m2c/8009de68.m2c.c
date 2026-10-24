? X_800a964c(?, ?);                                 /* extern */
? X_800ab060(?, ?);                                 /* extern */
? X_800ab094();                                     /* extern */

void FUN_8009de68(s32 arg4, s32 arg5, s32 arg6) {
    u32 temp_v1;
    void *temp_a0;
    void *temp_v0;
    void *temp_v1_2;

    temp_a0 = saved_reg_s1->unk-6568;
    temp_a0->unkEB = (s8) ((saved_reg_s0->unk8E < temp_a0->unk8E) << 7);
    temp_v0 = *(void **)0x800C9A98;
    temp_v1 = (u32) (temp_v0->unkEB & 0x80) >> 4;
    temp_v0->unkEA = (s8) temp_v1;
    temp_v0->unkEB = (u8) temp_v1;
    if (temp_v1 < 9U) {
        X_800ab060(0x11, 0x80);
        return;
    }
    temp_v1_2 = *(void **)0x800C9A98;
    temp_v1_2->unkF4 = (u8) (temp_v1_2->unkF4 | 2);
    X_800a964c(0x12, 0x80);
    (*(void *)0x800C9A98)->unk0 = 0x800AB094;
    X_800ab094();
}
