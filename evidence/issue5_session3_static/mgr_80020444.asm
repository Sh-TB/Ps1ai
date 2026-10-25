80020444 addiu   $sp, $sp, -0x20
80020448 sw      $s0, 0x18($sp)
8002044c move    $s0, $a0
80020450 move    $a0, $a1
80020454 move    $a1, $a2
80020458 move    $v1, $a3
8002045c sw      $ra, 0x1c($sp)
80020460 beqz    $a0, 0x80020590
80020464 sw      $zero, 0x10($sp)
80020468 lui     $v0, 0x800f
8002046c addiu   $v0, $v0, -0x46d8
80020470 beq     $a0, $v0, 0x800204a4
80020474 lui     $v0, 0x800f
80020478 addiu   $v0, $v0, -0x3660
8002047c beq     $a0, $v0, 0x800204a4
80020480 nop     
80020484 sll     $a1, $a2, 0x10
80020488 sra     $a1, $a1, 0x10
8002048c sll     $a2, $a3, 0x10
80020490 sra     $a2, $a2, 0x10
80020494 jal     0x80021830
80020498 addiu   $a3, $sp, 0x10
8002049c j       0x8001e2b8
800204a0 move    $a1, $v0
800204a4 sll     $a1, $a1, 0x10
800204a8 sra     $a1, $a1, 0x10
800204ac sll     $a2, $v1, 0x10
800204b0 jal     0x80024584
800204b4 sra     $a2, $a2, 0x10
800204b8 move    $a0, $v0
800204bc move    $a1, $a0
800204c0 andi    $v0, $a0, 0xe0
800204c4 lui     $v1, 0x800f
800204c8 lw      $v1, -0x4a18($v1)
800204cc srl     $v0, $v0, 5
800204d0 beqz    $v1, 0x800204ec
800204d4 sh      $v0, 0x10($sp)
800204d8 andi    $v0, $v0, 0xffff
800204dc addu    $v0, $v1, $v0
800204e0 lbu     $v0, ($v0)
800204e4 nop     
800204e8 sh      $v0, 0x10($sp)
800204ec lhu     $v1, 0x10($sp)
800204f0 addiu   $v0, $zero, 0xb
800204f4 bne     $v1, $v0, 0x8002051c
800204f8 andi    $v0, $a0, 0xf
800204fc addiu   $v1, $sp, 0x10
80020500 lhu     $v0, 2($v1)
80020504 nop     
80020508 sh      $v0, 0x10($sp)
8002050c andi    $v0, $a0, 0xf
80020510 addiu   $v0, $v0, 0x10
80020514 j       0x8001e2b0
80020518 sh      $zero, 2($v1)
8002051c sh      $v1, 0x12($sp)
80020520 sh      $v0, 0x10($sp)
80020524 andi    $a1, $a1, 0x10
80020528 lhu     $v1, 0x12($sp)
8002052c addiu   $v0, $zero, 1
80020530 bne     $v1, $v0, 0x80020558
80020534 andi    $v0, $a1, 0xffff
80020538 lui     $v0, 0x800f
8002053c lbu     $v0, -0x4a22($v0)
80020540 nop     
80020544 beqz    $v0, 0x80020558
80020548 andi    $v0, $a1, 0xffff
8002054c move    $a1, $zero
80020550 sh      $zero, 0x10($sp)
80020554 andi    $v0, $a1, 0xffff
80020558 beqz    $v0, 0x80020578
8002055c lui     $v1, 0x800f
80020560 lui     $a0, 0x800f
80020564 lhu     $v0, -0x4a30($a0)
80020568 lbu     $v1, -0x4a2e($v1)
8002056c ori     $v0, $v0, 8
80020570 beqz    $v1, 0x8002058c
80020574 sh      $v0, -0x4a30($a0)
80020578 lhu     $v0, 0x10($sp)
8002057c nop     
80020580 sltiu   $v0, $v0, 0x1f
80020584 bnez    $v0, 0x80020590
80020588 nop     
8002058c sh      $zero, 0x10($sp)
80020590 lw      $v0, 0x10($sp)
80020594 nop     
80020598 sw      $v0, ($s0)
8002059c move    $v0, $s0
800205a0 lw      $ra, 0x1c($sp)
800205a4 lw      $s0, 0x18($sp)
800205a8 jr      $ra
800205ac addiu   $sp, $sp, 0x20
800205b0 addiu   $sp, $sp, -0x18
800205b4 lui     $v0, 0x800f
800205b8 lw      $v1, -0x4a08($v0)
800205bc move    $a2, $v0
800205c0 sw      $ra, 0x10($sp)
800205c4 lw      $a0, ($v1)
800205c8 nop     
800205cc beqz    $a0, 0x800205fc
800205d0 move    $a1, $zero
800205d4 lw      $v0, 0x5c($a0)
800205d8 addiu   $v1, $v1, 4
800205dc beqz    $v0, 0x800205c4
800205e0 sw      $v1, -0x4a08($a2)
800205e4 lw      $v0, 8($v0)
800205e8 nop     
800205ec bnez    $v0, 0x80020600
800205f0 nop     
800205f4 j       0x8001e354
800205f8 nop     
800205fc addiu   $a1, $zero, 1
80020600 beqz    $a1, 0x80020614
80020604 nop     
80020608 jal     0x800216bc
8002060c nop     
80020610 move    $a0, $v0
80020614 lw      $ra, 0x10($sp)
80020618 move    $v0, $a0
8002061c jr      $ra
80020620 addiu   $sp, $sp, 0x18
80020624 lui     $v0, 0x800f
80020628 lbu     $v0, -0x4a22($v0)
8002062c nop     
80020630 beqz    $v0, 0x8002064c
80020634 move    $a3, $zero
80020638 lui     $v0, 0x800f
8002063c lbu     $v0, -0x4a0e($v0)
80020640 nop     
80020644 beqz    $v0, 0x80020654
80020648 nop     
8002064c jr      $ra
80020650 move    $v0, $zero
80020654 lw      $a2, 8($a0)
80020658 nop     
8002065c beqz    $a2, 0x80020704
80020660 lui     $v0, 0x800f
80020664 blez    $a2, 0x800206c8
80020668 lui     $v0, 0x800f
8002066c lhu     $v1, -0x4a20($v0)
80020670 addiu   $v0, $v0, -0x4a20
80020674 lhu     $v0, 4($v0)
80020678 sll     $a1, $v1, 0x10
8002067c sra     $v1, $a1, 0x10
80020680 andi    $a1, $a1, 0xffff
80020684 addu    $v0, $v0, $v1
80020688 sll     $v0, $v0, 0x10
8002068c or      $a1, $a1, $v0
80020690 lw      $v0, ($a0)
80020694 addiu   $a1, $a1, -1
80020698 subu    $a1, $a1, $v0
8002069c bgez    $a1, 0x800206ac
800206a0 slt     $v0, $a1, $a2
800206a4 move    $a1, $zero
800206a8 slt     $v0, $a1, $a2
800206ac beqz    $v0, 0x80020700
800206b0 lui     $v1, 0x800f
800206b4 addiu   $a3, $zero, 1
800206b8 addiu   $v0, $zero, 0xff
800206bc sw      $a1, 8($a0)
800206c0 j       0x8001e490
800206c4 sb      $v0, -0x4a77($v1)
800206c8 lhu     $v0, -0x4a20($v0)
800206cc lw      $v1, ($a0)
800206d0 sll     $a1, $v0, 0x10
800206d4 subu    $a1, $a1, $v1
800206d8 bltz    $a1, 0x800206e8
800206dc slt     $v0, $a2, $a1
800206e0 move    $a1, $zero
800206e4 slt     $v0, $a2, $a1
800206e8 beqz    $v0, 0x80020700
800206ec lui     $v1, 0x800f
800206f0 addiu   $a3, $zero, 1
800206f4 addiu   $v0, $zero, 0xff
800206f8 sw      $a1, 8($a0)
800206fc sb      $v0, -0x4a78($v1)
80020700 lui     $v0, 0x800f
80020704 lbu     $v0, -0x4a34($v0)
80020708 nop     
8002070c bnez    $v0, 0x800207d4
80020710 nop     
80020714 lw      $a2, 0xc($a0)
80020718 nop     
8002071c beqz    $a2, 0x800207d4
80020720 nop     
80020724 blez    $a2, 0x80020794
80020728 lui     $v0, 0x800f
8002072c addiu   $v0, $v0, -0x4a20
80020730 lhu     $v1, 2($v0)
80020734 lhu     $v0, 6($v0)
80020738 sll     $a1, $v1, 0x10
8002073c sra     $v1, $a1, 0x10
80020740 andi    $a1, $a1, 0xffff
80020744 addu    $v0, $v0, $v1
80020748 sll     $v0, $v0, 0x10
8002074c lui     $v1, 0x800f
80020750 or      $a1, $a1, $v0
80020754 lw      $v1, -0x4768($v1)
80020758 lw      $v0, 4($a0)
8002075c subu    $a1, $a1, $v1
80020760 addiu   $a1, $a1, -1
80020764 subu    $a1, $a1, $v0
80020768 bgez    $a1, 0x80020778
8002076c slt     $v0, $a1, $a2
80020770 move    $a1, $zero
80020774 slt     $v0, $a1, $a2
80020778 beqz    $v0, 0x800207d4
8002077c lui     $v1, 0x800f
80020780 addiu   $a3, $zero, 1
80020784 addiu   $v0, $zero, 0xff
80020788 sw      $a1, 0xc($a0)
8002078c j       0x8001e564
80020790 sb      $v0, -0x4a75($v1)
80020794 lui     $v0, 0x800f
80020798 lhu     $v0, -0x4a1e($v0)
8002079c nop     
800207a0 sll     $a1, $v0, 0x10
800207a4 lui     $v0, 0x800f
800207a8 lw      $v0, -0x4768($v0)
800207ac lw      $v1, 4($a0)
800207b0 subu    $a1, $a1, $v0
800207b4 subu    $a1, $a1, $v1
800207b8 slt     $v0, $a2, $a1
800207bc beqz    $v0, 0x800207d4
800207c0 lui     $v1, 0x800f
800207c4 addiu   $a3, $zero, 1
800207c8 addiu   $v0, $zero, 0xff
800207cc sw      $a1, 0xc($a0)
800207d0 sb      $v0, -0x4a76($v1)
800207d4 jr      $ra
800207d8 move    $v0, $a3
800207dc addiu   $sp, $sp, -0x40
800207e0 lui     $v0, 0x8001
800207e4 addiu   $v1, $v0, 0xcbc
800207e8 andi    $v0, $v1, 3
800207ec beqz    $v0, 0x8002084c
800207f0 move    $a1, $sp
800207f4 addiu   $v0, $v1, 0x30
800207f8 lwl     $a2, 3($v1)
800207fc lwr     $a2, ($v1)
80020800 lwl     $a3, 7($v1)
80020804 lwr     $a3, 4($v1)
80020808 lwl     $t0, 0xb($v1)
8002080c lwr     $t0, 8($v1)
80020810 lwl     $t1, 0xf($v1)
80020814 lwr     $t1, 0xc($v1)
80020818 swl     $a2, 3($a1)
8002081c swr     $a2, ($a1)
80020820 swl     $a3, 7($a1)
80020824 swr     $a3, 4($a1)
80020828 swl     $t0, 0xb($a1)
8002082c swr     $t0, 8($a1)
80020830 swl     $t1, 0xf($a1)
80020834 swr     $t1, 0xc($a1)
80020838 addiu   $v1, $v1, 0x10
8002083c bne     $v1, $v0, 0x800207f8
80020840 addiu   $a1, $a1, 0x10
80020844 j       0x8001e610
80020848 sll     $v0, $a0, 0x10
8002084c addiu   $v0, $v1, 0x30
80020850 lw      $a2, ($v1)
80020854 lw      $a3, 4($v1)
80020858 lw      $t0, 8($v1)
8002085c lw      $t1, 0xc($v1)
80020860 sw      $a2, ($a1)
80020864 sw      $a3, 4($a1)
80020868 sw      $t0, 8($a1)
8002086c sw      $t1, 0xc($a1)
80020870 addiu   $v1, $v1, 0x10
80020874 bne     $v1, $v0, 0x80020850
80020878 addiu   $a1, $a1, 0x10
8002087c sll     $v0, $a0, 0x10
80020880 sra     $v0, $v0, 0xf
80020884 addu    $v0, $sp, $v0
80020888 lwl     $a2, 3($v1)
8002088c lwr     $a2, ($v1)
80020890 lwl     $a3, 7($v1)
80020894 lwr     $a3, 4($v1)
80020898 lwl     $t0, 0xb($v1)
8002089c lwr     $t0, 8($v1)
800208a0 swl     $a2, 3($a1)
800208a4 swr     $a2, ($a1)
800208a8 swl     $a3, 7($a1)
800208ac swr     $a3, 4($a1)
800208b0 swl     $t0, 0xb($a1)
800208b4 swr     $t0, 8($a1)
800208b8 lhu     $v0, ($v0)
800208bc jr      $ra
800208c0 addiu   $sp, $sp, 0x40
800208c4 addiu   $sp, $sp, -0x20
800208c8 lui     $t1, 7
800208cc ori     $t1, $t1, 0xffff
800208d0 lui     $a3, 7
800208d4 ori     $a3, $a3, 0xffff
800208d8 move    $t0, $zero
800208dc lui     $v0, 0x8001
800208e0 sll     $a2, $a2, 0x10
800208e4 sra     $a2, $a2, 0x10
800208e8 addiu   $t5, $v0, 0xcf8
800208ec lwl     $t2, 3($t5)
800208f0 lwr     $t2, ($t5)
800208f4 lwl     $t3, 7($t5)
800208f8 lwr     $t3, 4($t5)
800208fc lwl     $t4, 0xb($t5)
80020900 lwr     $t4, 8($t5)
80020904 swl     $t2, 3($sp)
80020908 swr     $t2, ($sp)
8002090c swl     $t3, 7($sp)
80020910 swr     $t3, 4($sp)
80020914 swl     $t4, 0xb($sp)
80020918 swr     $t4, 8($sp)
8002091c lwl     $t2, 0xf($t5)
80020920 lwr     $t2, 0xc($t5)
80020924 lwl     $t3, 0x13($t5)
80020928 lwr     $t3, 0x10($t5)
8002092c lwl     $t4, 0x17($t5)
80020930 lwr     $t4, 0x14($t5)
80020934 swl     $t2, 0xf($sp)
80020938 swr     $t2, 0xc($sp)
8002093c swl     $t3, 0x13($sp)
80020940 swr     $t3, 0x10($sp)
80020944 swl     $t4, 0x17($sp)
80020948 swr     $t4, 0x14($sp)
8002094c lwl     $t2, 0x1b($t5)
80020950 lwr     $t2, 0x18($t5)
80020954 lb      $t3, 0x1c($t5)
80020958 lb      $t4, 0x1d($t5)
8002095c swl     $t2, 0x1b($sp)
80020960 swr     $t2, 0x18($sp)
80020964 sb      $t3, 0x1c($sp)
80020968 sb      $t4, 0x1d($sp)
8002096c addu    $v0, $sp, $a2
80020970 lw      $v1, 4($a1)
80020974 lbu     $a2, ($v0)
80020978 nop     
8002097c sltiu   $v0, $a2, 0xf
80020980 beqz    $v0, 0x80020a98
80020984 and     $a3, $v1, $a3
80020988 lui     $v0, 0x8001
8002098c addiu   $v0, $v0, 0xd1c
80020990 sll     $v1, $a2, 2
80020994 addu    $v1, $v1, $v0
80020998 lw      $v0, ($v1)
8002099c nop     
800209a0 jr      $v0
800209a4 nop     
800209a8 j       0x8001e74c
800209ac lui     $v0, 0xfffe
800209b0 j       0x8001e74c
800209b4 lui     $v0, 0xfffc
800209b8 lui     $v0, 0xfffa
800209bc addu    $a3, $a3, $v0
800209c0 lui     $v0, 1
800209c4 ori     $v0, $v0, 0xffff
800209c8 sltu    $v0, $v0, $a3
800209cc bnez    $v0, 0x80020a9c
800209d0 addiu   $v0, $zero, 3
800209d4 j       0x8001e82c
800209d8 addiu   $t0, $zero, 1
800209dc lw      $v0, ($a1)
800209e0 addiu   $t0, $zero, 0xf
800209e4 and     $t1, $t1, $v0
800209e8 subu    $a3, $a3, $t1
800209ec j       0x8001e828
800209f0 addiu   $a3, $a3, -1
800209f4 lui     $v0, 0xfffa
800209f8 j       0x8001e7c4
800209fc addu    $a3, $a3, $v0
80020a00 lui     $v0, 0xfffc
80020a04 j       0x8001e7c4
80020a08 addu    $a3, $a3, $v0
80020a0c lui     $v1, 0xfffe
80020a10 addu    $a3, $a3, $v1
80020a14 lui     $v0, 1
80020a18 ori     $v0, $v0, 0xffff
80020a1c sltu    $v0, $v0, $a3
80020a20 bnez    $v0, 0x80020a2c
80020a24 nop     
80020a28 addiu   $t0, $zero, 2
80020a2c j       0x8001e828
80020a30 addu    $a3, $a3, $v1
80020a34 lui     $v0, 1
80020a38 ori     $v0, $v0, 0xffff
80020a3c sltu    $v0, $v0, $a3
80020a40 bnez    $v0, 0x80020a4c
80020a44 lui     $v0, 0xfffe
80020a48 addiu   $t0, $zero, 2
80020a4c j       0x8001e828
80020a50 addu    $a3, $a3, $v0
80020a54 addiu   $t0, $zero, 0xf
80020a58 lw      $a3, 4($a1)
80020a5c lw      $v0, ($a1)
80020a60 nor     $a3, $zero, $a3
80020a64 and     $a3, $a3, $t1
80020a68 and     $t1, $t1, $v0
80020a6c j       0x8001e828
80020a70 swr     $s7, -0x21d2($v0)
80020a74 .byte   0xc7, 0x41, 0x61, 0x6a
80020a78 .byte   0x58, 0x43, 0xd2, 0xd2
80020a7c .byte   0xa7, 0x23, 0xc7, 0x44
80020a80 .byte   0xef, 0x5e, 0x2e, 0xee
80020a84 ldc2    $9, -0x396b($t1)
80020a88 j       0x82529bcc
80020a8c .byte   0xba, 0xec, 0x7f, 0x4f
80020a90 lwc2    $19, 0x4d3c($t6)
80020a94 addiu   $s2, $a1, -0x6a7c
80020a98 sdc2    $24, 0x604($s6)
80020a9c .byte   0x22, 0x8a, 0xf7, 0xb1
80020aa0 .byte   0x94, 0x20, 0xd9, 0x64
80020aa4 .byte   0x05, 0x38, 0x55, 0x5b
80020aa8 .byte   0x2e, 0x92, 0xf7, 0x58
80020aac .byte   0xbb, 0x71, 0xa7, 0x3d
80020ab0 sw      $t9, -0x1575($a3)
80020ab4 .byte   0xd6, 0x46, 0xae, 0x5d
80020ab8 j       0x8758d244
80020abc xori    $s3, $t9, 0xd5d4
80020ac0 bc0fl   $cc2, 0x8001843c
80020ac4 pref    7, -0x7bcb($t0)
80020ac8 .byte   0xa2, 0xb3, 0xde, 0xb5
80020acc lbu     $s5, 0x512b($sp)
80020ad0 jalx    0x8ad556dc
80020ad4 sltiu   $fp, $a2, -0x6518
80020ad8 .byte   0xaa, 0xc1, 0x5c, 0x9e
80020adc pref    0x18, -0x41f2($t7)
80020ae0 sh      $v0, -0x520c($zero)
80020ae4 swc1    $f31, 0xb20($t3)
80020ae8 lwc2    $7, 0x7e6($s0)
80020aec pref    0x11, 0x4de7($t3)
80020af0 .byte   0xa0, 0x8b, 0xab, 0x3e
80020af4 j       0x83cd7ae4
80020af8 j       0x891acb20
80020afc jal     0x8972595c
80020b00 lbu     $s3, 0x78be($t5)
80020b04 bz.v    $w31, 0x800126d0
80020b08 lhu     $a1, 0x5712($s4)
80020b0c .byte   0x99, 0x14, 0x03, 0x00
80020b10 .byte   0x0b, 0x29, 0xf4, 0x63
80020b14 .byte   0x85, 0xc4, 0xf8, 0x68
80020b18 lwr     $v0, -0x6e6f($a2)
80020b1c lwl     $t3, -0x2b34($a1)
80020b20 ll      $t3, 0x502d($t6)
80020b24 sdc1    $f0, 0x2db8($a2)
80020b28 sltiu   $s3, $v0, -0x67ea
80020b2c sh      $t2, 0x5f73($v0)
80020b30 bnel    $fp, $t1, 0x80017670
80020b34 jal     0x8c2f9af8
80020b38 bne     $t4, $s0, 0x80024658
80020b3c sh      $t0, 0x355a($a1)
80020b40 .byte   0x50, 0xfd, 0x2d, 0xdf
80020b44 xori    $s6, $sp, 0xf8f4
80020b48 nmadd.s $f21, $f22, $f19, $f0
80020b4c .byte   0x40, 0xb4, 0xe6, 0xf0
80020b50 bne     $t9, $v0, 0x80002f50
80020b54 addiu   $v0, $k0, 0x165f
80020b58 .byte   0xc2, 0xc2, 0x14, 0xf1
80020b5c lwc1    $f26, -0x4e0b($a2)
80020b60 .byte   0x4c, 0x89, 0xf6, 0x4b
80020b64 swl     $t7, -0x46df($t9)
80020b68 ll      $s0, 0x4940($t9)
80020b6c .byte   0xd7, 0x7e, 0x74, 0x6e
80020b70 swc2    $24, -0x4771($t1)
80020b74 .byte   0xcf, 0xaf, 0x43, 0x6a
80020b78 swc1    $f13, -0x384c($ra)
80020b7c sh      $t6, -0x404($t4)
80020b80 .byte   0x2d, 0xc2, 0x2a, 0x66
80020b84 .byte   0x00, 0x9e, 0x94, 0xed
80020b88 .byte   0x00, 0xff, 0xff, 0xff
80020b8c .byte   0xff, 0xff, 0xff, 0xff
80020b90 .byte   0xff, 0xff, 0xff, 0x00
80020b94 .byte   0x00, 0x35, 0x09, 0x02
80020b98 sll     $zero, $t0, 0
80020b9c sll     $zero, $t0, 0
80020ba0 subu    $a3, $a3, $t1
80020ba4 j       0x8001e828
80020ba8 move    $t0, $zero
80020bac lw      $v0, 8($a1)
80020bb0 nop     
80020bb4 bltz    $v0, 0x80020bc8
80020bb8 addiu   $t0, $zero, 4
80020bbc j       0x8001e828
80020bc0 addiu   $t0, $zero, 3
80020bc4 addiu   $t0, $zero, 4
80020bc8 addiu   $v0, $zero, 3
80020bcc bne     $t0, $v0, 0x80020bfc
80020bd0 addiu   $v0, $zero, 4
80020bd4 lui     $v0, 0x800f
80020bd8 lbu     $v0, -0x4a33($v0)
80020bdc nop     
80020be0 bnez    $v0, 0x80020c14
80020be4 lui     $v0, 7
80020be8 lw      $a3, ($a1)
80020bec ori     $v0, $v0, 0xffff
80020bf0 and     $a3, $a3, $v0
80020bf4 j       0x8001e88c
80020bf8 nor     $a3, $zero, $a3
80020bfc bne     $t0, $v0, 0x80020c2c
80020c00 lui     $v0, 0x800f
80020c04 lbu     $v0, -0x4a33($v0)
80020c08 nop     
80020c0c beqz    $v0, 0x80020c1c
80020c10 lui     $v0, 7
80020c14 j       0x8001e88c
80020c18 move    $t0, $zero
80020c1c lw      $a3, ($a1)
80020c20 ori     $v0, $v0, 0xffff
80020c24 nor     $a3, $zero, $a3
80020c28 and     $a3, $a3, $v0
80020c2c bnez    $t0, 0x80020c3c
80020c30 addiu   $v0, $zero, 1
80020c34 j       0x8001e8d8
80020c38 lui     $a3, 0x8000
80020c3c bne     $t0, $v0, 0x80020c5c
80020c40 addiu   $v0, $zero, 2
80020c44 lw      $v0, ($a1)
80020c48 sll     $a3, $a3, 2
80020c4c and     $t1, $t1, $v0
80020c50 subu    $a3, $a3, $t1
80020c54 j       0x8001e8d8
80020c58 addiu   $a3, $a3, -1
80020c5c bne     $t0, $v0, 0x80020c78
80020c60 nop     
80020c64 lw      $v0, ($a1)
80020c68 sll     $a3, $a3, 2
80020c6c and     $t1, $t1, $v0
80020c70 addu    $a3, $a3, $t1
80020c74 nor     $a3, $zero, $a3
80020c78 sw      $a3, ($a0)
80020c7c move    $v0, $a0
80020c80 jr      $ra
80020c84 addiu   $sp, $sp, 0x20
80020c88 addiu   $sp, $sp, -0x20
80020c8c move    $t1, $zero
80020c90 lui     $t0, 7
80020c94 lui     $a3, 7
80020c98 ori     $a3, $a3, 0xffff
80020c9c lui     $v0, 0x8001
80020ca0 sll     $a2, $a2, 0x10
80020ca4 sra     $a2, $a2, 0x10
80020ca8 addiu   $t5, $v0, 0xd58
80020cac lwl     $t2, 3($t5)
80020cb0 lwr     $t2, ($t5)
80020cb4 lwl     $t3, 7($t5)
80020cb8 lwr     $t3, 4($t5)
80020cbc lwl     $t4, 0xb($t5)
80020cc0 lwr     $t4, 8($t5)
80020cc4 swl     $t2, 3($sp)
80020cc8 swr     $t2, ($sp)
80020ccc swl     $t3, 7($sp)
80020cd0 swr     $t3, 4($sp)
80020cd4 swl     $t4, 0xb($sp)
80020cd8 swr     $t4, 8($sp)
80020cdc lwl     $t2, 0xf($t5)
80020ce0 lwr     $t2, 0xc($t5)
80020ce4 lwl     $t3, 0x13($t5)
80020ce8 lwr     $t3, 0x10($t5)
80020cec lwl     $t4, 0x17($t5)
80020cf0 lwr     $t4, 0x14($t5)
80020cf4 swl     $t2, 0xf($sp)
80020cf8 swr     $t2, 0xc($sp)
80020cfc swl     $t3, 0x13($sp)
80020d00 swr     $t3, 0x10($sp)
80020d04 swl     $t4, 0x17($sp)
80020d08 swr     $t4, 0x14($sp)
80020d0c lwl     $t2, 0x1b($t5)
80020d10 lwr     $t2, 0x18($t5)
80020d14 lb      $t3, 0x1c($t5)
80020d18 lb      $t4, 0x1d($t5)
80020d1c swl     $t2, 0x1b($sp)
80020d20 swr     $t2, 0x18($sp)
80020d24 sb      $t3, 0x1c($sp)
80020d28 sb      $t4, 0x1d($sp)
80020d2c addu    $v0, $sp, $a2
80020d30 lw      $v1, ($a1)
80020d34 lbu     $a2, ($v0)
80020d38 and     $a3, $v1, $a3
80020d3c addiu   $v1, $a2, -1
80020d40 sltiu   $v0, $v1, 0xf
80020d44 beqz    $v0, 0x80020ebc
80020d48 ori     $t0, $t0, 0xffff
80020d4c lui     $v0, 0x8001
80020d50 addiu   $v0, $v0, 0xd7c
80020d54 sll     $v1, $v1, 2
80020d58 addu    $v1, $v1, $v0
80020d5c lw      $v0, ($v1)
80020d60 nop     
80020d64 jr      $v0
80020d68 nop     
80020d6c bgez    $a3, 0x80020d78
80020d70 move    $v1, $a3
80020d74 addiu   $v1, $a3, 3
80020d78 lw      $v0, 4($a1)
80020d7c sra     $a3, $v1, 2
80020d80 andi    $v1, $a2, 0xff
80020d84 and     $t0, $t0, $v0
80020d88 addiu   $v0, $zero, 3
80020d8c beq     $v1, $v0, 0x80020dcc
80020d90 subu    $a3, $a3, $t0
80020d94 slti    $v0, $v1, 4
80020d98 beqz    $v0, 0x80020db0
80020d9c addiu   $v0, $zero, 2
80020da0 beq     $v1, $v0, 0x80020dc4
80020da4 addiu   $t1, $zero, 0xf
80020da8 j       0x8001eb20
80020dac addiu   $v0, $zero, 1
80020db0 addiu   $v0, $zero, 4
80020db4 beq     $v1, $v0, 0x80020dd4
80020db8 addiu   $t1, $zero, 0xf
80020dbc j       0x8001eb20
80020dc0 addiu   $v0, $zero, 1
80020dc4 j       0x8001eab8
80020dc8 lui     $v0, 2
80020dcc j       0x8001eab8
80020dd0 lui     $v0, 4
80020dd4 j       0x8001eab8
80020dd8 lui     $v0, 6
80020ddc lw      $v0, 4($a1)
80020de0 j       0x8001ead8
80020de4 addiu   $t1, $zero, 0xf
80020de8 bgez    $a3, 0x80020df4
80020dec move    $v0, $a3
80020df0 addiu   $v0, $a3, 3
80020df4 sra     $a3, $v0, 2
80020df8 lw      $v0, 4($a1)
80020dfc subu    $a3, $t0, $a3
80020e00 andi    $v1, $a2, 0xff
80020e04 and     $t0, $t0, $v0
80020e08 addiu   $v0, $zero, 8
80020e0c beq     $v1, $v0, 0x80020e4c
80020e10 subu    $a3, $a3, $t0
80020e14 slti    $v0, $v1, 9
80020e18 beqz    $v0, 0x80020e30
80020e1c addiu   $v0, $zero, 7
80020e20 beq     $v1, $v0, 0x80020e44
80020e24 addiu   $t1, $zero, 0xf
80020e28 j       0x8001eb20
80020e2c addiu   $v0, $zero, 1
80020e30 addiu   $v0, $zero, 9
80020e34 beq     $v1, $v0, 0x80020e54
80020e38 addiu   $t1, $zero, 0xf
80020e3c j       0x8001eb20
80020e40 addiu   $v0, $zero, 1
80020e44 j       0x8001eab8
80020e48 lui     $v0, 0xfffe
80020e4c j       0x8001eab8
80020e50 lui     $v0, 0xfffc
80020e54 lui     $v0, 0xfffa
80020e58 addu    $a3, $a3, $v0
80020e5c j       0x8001eb1c
80020e60 addiu   $t1, $zero, 0xf
80020e64 addiu   $t1, $zero, 0xf
80020e68 lw      $a3, ($a1)
80020e6c lw      $v0, 4($a1)
80020e70 nor     $a3, $zero, $a3
80020e74 and     $a3, $a3, $t0
80020e78 and     $t0, $t0, $v0
80020e7c j       0x8001eb1c
80020e80 subu    $a3, $a3, $t0
80020e84 lui     $v0, 0x800f
80020e88 lbu     $v0, -0x4a33($v0)
80020e8c nop     
80020e90 bnez    $v0, 0x80020ec0
80020e94 addiu   $v0, $zero, 1
80020e98 lw      $v0, 0xc($a1)
80020e9c nop     
80020ea0 bltz    $v0, 0x80020ebc
80020ea4 addiu   $t1, $zero, 2
80020ea8 j       0x8001eb1c
80020eac addiu   $t1, $zero, 1
80020eb0 j       0x8001eb1c
80020eb4 addiu   $t1, $zero, 2
80020eb8 addiu   $t1, $zero, 3
80020ebc addiu   $v0, $zero, 1
80020ec0 bne     $t1, $v0, 0x80020ee0
80020ec4 addiu   $v0, $zero, 2
80020ec8 lw      $a3, 4($a1)
80020ecc lui     $v0, 7
80020ed0 ori     $v0, $v0, 0xffff
80020ed4 and     $a3, $a3, $v0
80020ed8 j       0x8001eb90
80020edc nor     $a3, $zero, $a3
80020ee0 bne     $t1, $v0, 0x80020f00
80020ee4 addiu   $v0, $zero, 3
80020ee8 lw      $a3, 4($a1)
80020eec lui     $v0, 7
80020ef0 ori     $v0, $v0, 0xffff
80020ef4 nor     $a3, $zero, $a3
80020ef8 j       0x8001eb90
80020efc and     $a3, $a3, $v0
80020f00 bne     $t1, $v0, 0x80020f24
80020f04 lui     $v0, 7
80020f08 lw      $a3, 4($a1)
80020f0c ori     $v0, $v0, 0xffff
80020f10 nor     $a3, $zero, $a3
80020f14 and     $a3, $a3, $v0
80020f18 lui     $v0, 0xfffc
80020f1c j       0x8001eb90
80020f20 addu    $a3, $a3, $v0
80020f24 bnez    $t1, 0x80020f30
80020f28 nop     
80020f2c lui     $a3, 0x8000
80020f30 sw      $a3, ($a0)
80020f34 move    $v0, $a0
80020f38 jr      $ra
80020f3c addiu   $sp, $sp, 0x20
80020f40 addiu   $sp, $sp, -0x20
80020f44 lui     $v0, 0x8001
80020f48 addiu   $t4, $v0, 0xdb8
80020f4c lwl     $t1, 3($t4)
80020f50 lwr     $t1, ($t4)
80020f54 lwl     $t2, 7($t4)
80020f58 lwr     $t2, 4($t4)
80020f5c lwl     $t3, 0xb($t4)
80020f60 lwr     $t3, 8($t4)
80020f64 swl     $t1, 3($sp)
80020f68 swr     $t1, ($sp)
80020f6c swl     $t2, 7($sp)
80020f70 swr     $t2, 4($sp)
80020f74 swl     $t3, 0xb($sp)
80020f78 swr     $t3, 8($sp)
80020f7c lwl     $t1, 0xf($t4)
80020f80 lwr     $t1, 0xc($t4)
80020f84 lwl     $t2, 0x13($t4)
80020f88 lwr     $t2, 0x10($t4)
80020f8c lwl     $t3, 0x17($t4)
80020f90 lwr     $t3, 0x14($t4)
80020f94 swl     $t1, 0xf($sp)
80020f98 swr     $t1, 0xc($sp)
80020f9c swl     $t2, 0x13($sp)
80020fa0 swr     $t2, 0x10($sp)
80020fa4 swl     $t3, 0x17($sp)
80020fa8 swr     $t3, 0x14($sp)
80020fac lwl     $t1, 0x1b($t4)
80020fb0 lwr     $t1, 0x18($t4)
80020fb4 lb      $t2, 0x1c($t4)
80020fb8 lb      $t3, 0x1d($t4)
80020fbc swl     $t1, 0x1b($sp)
80020fc0 swr     $t1, 0x18($sp)
80020fc4 sb      $t2, 0x1c($sp)
80020fc8 sb      $t3, 0x1d($sp)
80020fcc sll     $v0, $a3, 0x10
80020fd0 sra     $v0, $v0, 0x10
80020fd4 addu    $v0, $sp, $v0
80020fd8 lbu     $v0, ($v0)
80020fdc nop     
80020fe0 addiu   $v1, $v0, -1
80020fe4 sltiu   $v0, $v1, 0xd
80020fe8 beqz    $v0, 0x8002110c
80020fec move    $t0, $zero
80020ff0 lui     $v0, 0x8001
80020ff4 addiu   $v0, $v0, 0xddc
80020ff8 sll     $v1, $v1, 2
80020ffc addu    $v1, $v1, $v0
80021000 lw      $v0, ($v1)
80021004 nop     
80021008 jr      $v0
8002100c nop     
80021010 sll     $v0, $a2, 2
80021014 slt     $v0, $a1, $v0
80021018 beqz    $v0, 0x8002110c
8002101c nop     
80021020 j       0x8001ed6c
80021024 addiu   $t0, $zero, 1
80021028 slt     $v0, $a1, $a2
8002102c beqz    $v0, 0x8002110c
80021030 nop     
80021034 j       0x8001ed6c
80021038 addiu   $t0, $zero, 1
8002103c sll     $v0, $a2, 2
80021040 negu    $v0, $v0
80021044 slt     $v0, $v0, $a1
80021048 beqz    $v0, 0x8002110c
8002104c nop     
80021050 j       0x8001ed6c
80021054 addiu   $t0, $zero, 1
80021058 negu    $v0, $a1
8002105c slt     $v0, $v0, $a2
80021060 beqz    $v0, 0x8002110c
80021064 nop     
80021068 j       0x8001ed6c
8002106c addiu   $t0, $zero, 1
80021070 blez    $a2, 0x8002110c
80021074 nop     
80021078 j       0x8001ed6c
8002107c addiu   $t0, $zero, 1
80021080 bgez    $a2, 0x8002110c
80021084 nop     
80021088 j       0x8001ed6c
8002108c addiu   $t0, $zero, 1
80021090 sll     $v0, $a2, 2
80021094 slt     $v0, $v0, $a1
80021098 beqz    $v0, 0x8002110c
8002109c nop     
800210a0 j       0x8001ed6c
800210a4 addiu   $t0, $zero, 1
800210a8 slt     $v0, $a2, $a1
800210ac beqz    $v0, 0x8002110c
800210b0 nop     
800210b4 j       0x8001ed6c
800210b8 addiu   $t0, $zero, 1
800210bc sll     $v0, $a2, 2
800210c0 negu    $v0, $v0
800210c4 slt     $v0, $a1, $v0
800210c8 beqz    $v0, 0x8002110c
800210cc nop     
800210d0 j       0x8001ed6c
800210d4 addiu   $t0, $zero, 1
800210d8 negu    $v0, $a1
800210dc slt     $v0, $a2, $v0
800210e0 beqz    $v0, 0x8002110c
800210e4 nop     
800210e8 j       0x8001ed6c
800210ec addiu   $t0, $zero, 1
800210f0 blez    $a1, 0x8002110c
800210f4 nop     
800210f8 j       0x8001ed6c
800210fc addiu   $t0, $zero, 1
80021100 bgez    $a1, 0x8002110c
80021104 nop     
80021108 addiu   $t0, $zero, 1
8002110c beqz    $t0, 0x80021118
80021110 nop     
80021114 move    $a3, $zero
80021118 sw      $a3, ($a0)
8002111c move    $v0, $a0
80021120 jr      $ra
80021124 addiu   $sp, $sp, 0x20