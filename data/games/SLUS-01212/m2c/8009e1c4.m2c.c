s16 X_8005cad0(?);                                  /* extern */
? X_800a9334();                                     /* extern */
? X_800a964c(s16, ? *, ?, ?);                       /* extern */
? X_800ab424(s8 *, ? *, ?, ?);                      /* extern */
? X_800ab474();                                     /* extern */

void FUN_8009e1c4(? arg2, ? arg4, s8 arg12, s32 arg20) {
    ? temp_a2;
    ? temp_a3;
    void *temp_v0;
    void *temp_v1;

    arg10 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg11 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg12 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg13 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg14 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg15 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg16 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg17 = (unaligned s32) M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    temp_a2 = M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    temp_a3 = M2C_ERROR(/* Unable to handle lwr; missing a corresponding lwl */);
    arg18 = (unaligned s32) temp_a2;
    arg19 = (unaligned s32) temp_a3;
    temp_v0 = *(void **)0x800C9A98;
    if (!(temp_v0->unk27 & 1)) {
        X_800ab424(&arg12, &arg4, temp_a2, temp_a3);
        return;
    }
    X_800a964c(*(&arg12 + ((temp_v0->unkEA & 0xF & 0xFF) * 2)), &arg4, temp_a2, temp_a3);
    X_800a9334();
    temp_v1 = *(void *)0x800C9A98;
    temp_v1->unkDA = X_8005cad0(0x8009B558);
    temp_v1->unk0 = 0x800AB474;
    X_800ab474();
}
