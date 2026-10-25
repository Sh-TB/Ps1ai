80021128 addiu   $sp, $sp, -0x28
8002112c move    $t0, $a0
80021130 lui     $v0, 0x8001
80021134 addiu   $t4, $v0, 0xdb8
80021138 lwl     $t1, 3($t4)
8002113c lwr     $t1, ($t4)
80021140 lwl     $t2, 7($t4)
80021144 lwr     $t2, 4($t4)
80021148 lwl     $t3, 0xb($t4)
8002114c lwr     $t3, 8($t4)
80021150 swl     $t1, 3($sp)
80021154 swr     $t1, ($sp)
80021158 swl     $t2, 7($sp)
8002115c swr     $t2, 4($sp)
80021160 swl     $t3, 0xb($sp)
80021164 swr     $t3, 8($sp)
80021168 lwl     $t1, 0xf($t4)
8002116c lwr     $t1, 0xc($t4)
80021170 lwl     $t2, 0x13($t4)
80021174 lwr     $t2, 0x10($t4)
80021178 lwl     $t3, 0x17($t4)
8002117c lwr     $t3, 0x14($t4)
80021180 swl     $t1, 0xf($sp)
80021184 swr     $t1, 0xc($sp)
80021188 swl     $t2, 0x13($sp)
8002118c swr     $t2, 0x10($sp)
80021190 swl     $t3, 0x17($sp)
80021194 swr     $t3, 0x14($sp)
80021198 lwl     $t1, 0x1b($t4)
8002119c lwr     $t1, 0x18($t4)
800211a0 lb      $t2, 0x1c($t4)
800211a4 lb      $t3, 0x1d($t4)
800211a8 swl     $t1, 0x1b($sp)
800211ac swr     $t1, 0x18($sp)
800211b0 sb      $t2, 0x1c($sp)
800211b4 sb      $t3, 0x1d($sp)
800211b8 lw      $v0, 8($t0)
800211bc nop     
800211c0 bnez    $v0, 0x800211d8
800211c4 lui     $v0, 0x800f
800211c8 lw      $v0, 0xc($t0)
800211cc nop     
800211d0 beqz    $v0, 0x800219c0
800211d4 lui     $v0, 0x800f
800211d8 lw      $a3, -0x4a78($v0)
800211dc lh      $v0, -0x4a78($v0)
800211e0 addiu   $v1, $zero, -1
800211e4 beq     $v0, $v1, 0x800211f4
800211e8 sra     $v0, $a3, 0x10
800211ec bne     $v0, $v1, 0x80021200
800211f0 lui     $v0, 0x800f
800211f4 sw      $zero, 8($t0)
800211f8 j       0x8001f620
800211fc sw      $zero, 0xc($t0)
80021200 lhu     $v1, -0x4a3a($v0)
80021204 addiu   $v0, $zero, 9
80021208 bne     $v1, $v0, 0x80021214
8002120c sll     $v0, $a1, 0x10
80021210 ori     $a3, $a3, 0xffff
80021214 sra     $v0, $v0, 0x10
80021218 addu    $v0, $sp, $v0
8002121c lbu     $a0, ($v0)
80021220 nop     
80021224 addiu   $v1, $a0, -1
80021228 sltiu   $v0, $v1, 0xd
8002122c beqz    $v0, 0x800219c0
80021230 lui     $v0, 0x8001
80021234 addiu   $v0, $v0, 0xe14
80021238 sll     $v1, $v1, 2
8002123c addu    $v1, $v1, $v0
80021240 lw      $v0, ($v1)
80021244 nop     
80021248 jr      $v0
8002124c nop     
80021250 addiu   $v0, $zero, 8
80021254 bne     $a0, $v0, 0x80021298
80021258 lui     $a1, 0x800f
8002125c lui     $v1, 0x800f
80021260 addiu   $v0, $zero, -0x3600
80021264 lui     $a0, 0x800f
80021268 sh      $v0, -0x4a32($v1)
8002126c lui     $v1, 0x800f
80021270 lhu     $v0, -0x4a30($a0)
80021274 lbu     $v1, -0x4a76($v1)
80021278 ori     $v0, $v0, 0x12  <== ORI 0x12
8002127c beqz    $v1, 0x800212b0
80021280 sh      $v0, -0x4a30($a0)
80021284 lw      $v0, 0xc($t0)
80021288 nop     
8002128c addiu   $v0, $v0, -1
80021290 j       0x8001ef10
80021294 sw      $v0, 0xc($t0)
80021298 lui     $a0, 0x800f
8002129c lhu     $v0, -0x4a30($a1)
800212a0 addiu   $v1, $zero, 0x4a00
800212a4 sh      $v1, -0x4a32($a0)
800212a8 ori     $v0, $v0, 0x42  <== ORI 0x42
800212ac sh      $v0, -0x4a30($a1)
800212b0 beqz    $a3, 0x800213bc
800212b4 nop     
800212b8 lw      $a2, 0xc($t0)
800212bc lw      $v0, 8($t0)
800212c0 sll     $a2, $a2, 2
800212c4 subu    $a2, $a2, $v0
800212c8 beqz    $a2, 0x800219c0
800212cc nop     
800212d0 bltz    $a2, 0x800212e4
800212d4 lui     $v0, 0xffff
800212d8 and     $a2, $a2, $v0
800212dc j       0x8001ef4c
800212e0 ori     $a2, $a2, 0xff00
800212e4 and     $a2, $a2, $v0
800212e8 ori     $a2, $a2, 0xff
800212ec and     $v0, $a3, $a2
800212f0 lui     $v1, 0xffff
800212f4 and     $a3, $a3, $v1
800212f8 andi    $v0, $v0, 0xffff
800212fc or      $a3, $a3, $v0
80021300 sll     $v0, $a3, 0x10
80021304 beqz    $v0, 0x80021368
80021308 lui     $v0, 0x800f
8002130c addiu   $v0, $v0, -0x4a78
80021310 lhu     $v1, 2($v0)
80021314 nop     
80021318 or      $v1, $v1, $a3
8002131c sh      $v1, 2($v0)
80021320 sll     $v0, $a3, 0x18
80021324 beqz    $v0, 0x8002133c
80021328 nop     
8002132c lw      $v0, 8($t0)
80021330 nop     
80021334 addiu   $v0, $v0, 3
80021338 sw      $v0, 8($t0)
8002133c lw      $v1, 8($t0)
80021340 nop     
80021344 bgez    $v1, 0x80021350
80021348 nop     
8002134c addiu   $v1, $v1, 3
80021350 sra     $v1, $v1, 2
80021354 sw      $v1, 8($t0)
80021358 move    $v0, $v1
8002135c sll     $v0, $v0, 2
80021360 sw      $v1, 0xc($t0)
80021364 sw      $v0, 8($t0)
80021368 sra     $v1, $a3, 0x10
8002136c andi    $a3, $a3, 0xffff
80021370 nor     $v0, $zero, $a2
80021374 and     $v0, $v0, $v1
80021378 sll     $v0, $v0, 0x10
8002137c or      $a3, $a3, $v0
80021380 sra     $a0, $a3, 0x10
80021384 beqz    $a0, 0x800213b4
80021388 lui     $v1, 0x800f
8002138c lhu     $v0, -0x4a78($v1)
80021390 nop     
80021394 or      $v0, $v0, $a0
80021398 sh      $v0, -0x4a78($v1)
8002139c lw      $v1, 0xc($t0)
800213a0 ldc1    $f22, 0x148($sp)
800213a4 .byte   0xc5, 0xe8, 0x5c, 0x64
800213a8 pref    0x10, -0x4718($gp)
800213ac sdc1    $f13, -0x4c92($v1)
800213b0 .byte   0x81, 0x2a, 0x77, 0xf0
800213b4 swl     $s4, -0x24c2($t4)
800213b8 .byte   0x3b, 0xa7, 0xaa, 0x65
800213bc lw      $s6, -0x7dc5($s2)
800213c0 lwc1    $f26, 0x4e01($t8)
800213c4 swl     $s2, -0x57f6($s7)
800213c8 .byte   0xda, 0xa0, 0xa9, 0x72
800213cc addi    $t7, $sp, -0x25a4
800213d0 lhu     $t3, 0x12ba($k0)
800213d4 pref    9, 0x3e1e($t5)
800213d8 jal     0x8546e448
800213dc .byte   0x80, 0x97, 0x89, 0x63
800213e0 .byte   0xd3, 0xab, 0x6d, 0x60
800213e4 addiu   $ra, $t0, 0x728d
800213e8 ldc1    $f13, -0x6e5($t6)
800213ec beq     $t5, $a3, 0x80002884
800213f0 swc1    $f15, -0x64a7($s2)
800213f4 .byte   0x4c, 0x74, 0xa1, 0x49
800213f8 sh      $t7, -0x1ca9($s1)
800213fc ori     $fp, $t2, 0x447e
80021400 ldc2    $5, -0x4c38($t9)
80021404 lbu     $t4, -0x5ec3($ra)
80021408 swl     $gp, 0xd71($sp)
8002140c jalx    0x81e853c8
80021410 andi    $a0, $t4, 0x1d56
80021414 .byte   0xa7, 0xde, 0x7c, 0x3e
80021418 swc1    $f31, -0x68f1($v1)
8002141c .byte   0x9f, 0xa4, 0x49, 0x5b
80021420 .byte   0x90, 0xf9, 0x45, 0xee
80021424 .byte   0x07, 0xf6, 0x82, 0xf1
80021428 .byte   0x1a, 0x53, 0xc5, 0x61
8002142c .byte   0xcb, 0xf1, 0x6a, 0x44
80021430 jal     0x85fae414
80021434 lwc1    $f5, 0x6286($t6)
80021438 bltzl   $t6, 0x800139f8
8002143c .byte   0x27, 0x1f, 0x26, 0xdc
80021440 swr     $k1, -0x197c($s6)
80021444 sdc2    $27, 0x11a($zero)
80021448 lh      $ra, 0x7d0c($k1)
8002144c swc2    $9, 0x6215($v1)
80021450 addi    $v1, $t9, -0x1f5e
80021454 .byte   0x5f, 0x0f, 0x4f, 0x72
80021458 .byte   0x0b, 0xa3, 0xa4, 0x1f
8002145c lwc2    $21, -0x4a76($v0)
80021460 jalx    0x86bcd790
80021464 .byte   0x19, 0x0a, 0x1e, 0x5a
80021468 .byte   0xb6, 0x89, 0x12, 0xd2
8002146c lwc1    $f4, -0x74c5($t2)
80021470 .byte   0x40, 0xfb, 0xb9, 0xd3
80021474 addi    $t4, $a1, -0x65fb
80021478 slti    $v1, $sp, 0x3a9c
8002147c ldc1    $f20, 0x519($a1)
80021480 .byte   0xaf, 0xfa, 0x1b, 0xd2
80021484 bz.b    $w1, 0x8003b84c
80021488 sb      $a3, -0x40e9($s7)
8002148c sw      $v1, 0x3447($t2)
80021490 pref    0x14, 0xda6($k0)
80021494 .byte   0xf9, 0x65, 0x25, 0x5d
80021498 sw      $t1, -0x2a05($v1)
8002149c beql    $sp, $t2, 0x8000efd4
800214a0 sc      $a1, 0x564($t6)
800214a4 .byte   0x8a, 0xe5, 0x8f, 0x5f
800214a8 .byte   0x19, 0x94, 0x96, 0x1c
800214ac addiu   $at, $s2, -0x53eb
800214b0 lb      $t7, -0x156c($s7)
800214b4 ldc2    $25, 0x20c2($t0)
800214b8 .byte   0x00, 0xff, 0xff, 0xff
800214bc .byte   0xff, 0xff, 0xff, 0xff
800214c0 .byte   0xff, 0xff, 0xff, 0x00
800214c4 .byte   0x00, 0x35, 0x10, 0x02
800214c8 sll     $zero, $t0, 0
800214cc sll     $zero, $t0, 0
800214d0 nop     
800214d4 move    $v0, $v1
800214d8 sll     $v0, $v0, 2
800214dc sw      $v1, 8($t0)
800214e0 sw      $v0, 0xc($t0)
800214e4 bnez    $a3, 0x80021af0
800214e8 nop     
800214ec lw      $a2, 0xc($t0)
800214f0 lw      $v0, 8($t0)
800214f4 sll     $a2, $a2, 2
800214f8 beq     $a2, $v0, 0x80021af0
800214fc sll     $v0, $v0, 2
80021500 lw      $v1, 0xc($t0)
80021504 sw      $v0, 8($t0)
80021508 addu    $v1, $v0, $v1
8002150c andi    $v0, $v1, 8
80021510 beqz    $v0, 0x80021524
80021514 sw      $v1, 8($t0)
80021518 sra     $v0, $v1, 4
8002151c j       0x8001f058
80021520 addiu   $v0, $v0, 1
80021524 sra     $v0, $v1, 4
80021528 sw      $v0, 8($t0)
8002152c lw      $v1, 8($t0)
80021530 nop     
80021534 move    $v0, $v1
80021538 sll     $v0, $v0, 2
8002153c sw      $v1, 0xc($t0)
80021540 j       0x8001f620
80021544 sw      $v0, 8($t0)
80021548 addiu   $v0, $zero, 9
8002154c bne     $a0, $v0, 0x80021590
80021550 lui     $a1, 0x800f
80021554 lui     $v1, 0x800f
80021558 addiu   $v0, $zero, -0x2000
8002155c lui     $a0, 0x800f
80021560 sh      $v0, -0x4a32($v1)
80021564 lui     $v1, 0x800f
80021568 lhu     $v0, -0x4a30($a0)
8002156c lbu     $v1, -0x4a76($v1)
80021570 ori     $v0, $v0, 0x12  <== ORI 0x12
80021574 bnez    $v1, 0x800215a8
80021578 sh      $v0, -0x4a30($a0)
8002157c lw      $v0, 0xc($t0)
80021580 nop     
80021584 addiu   $v0, $v0, -1
80021588 j       0x8001f0d8
8002158c sw      $v0, 0xc($t0)
80021590 lui     $a0, 0x800f
80021594 lhu     $v0, -0x4a30($a1)
80021598 addiu   $v1, $zero, 0x6000
8002159c sh      $v1, -0x4a32($a0)
800215a0 ori     $v0, $v0, 0x42  <== ORI 0x42
800215a4 sh      $v0, -0x4a30($a1)
800215a8 beqz    $a3, 0x80021668
800215ac nop     
800215b0 lw      $v0, 0xc($t0)
800215b4 lw      $v1, 8($t0)
800215b8 nop     
800215bc beq     $v0, $v1, 0x80021af0
800215c0 slt     $v0, $v0, $v1
800215c4 bnez    $v0, 0x800215d8
800215c8 lui     $v0, 0xffff
800215cc and     $a2, $a2, $v0
800215d0 j       0x8001f110
800215d4 ori     $a2, $a2, 0xff00
800215d8 and     $a2, $a2, $v0
800215dc ori     $a2, $a2, 0xff
800215e0 and     $v0, $a3, $a2
800215e4 lui     $a0, 0xffff
800215e8 and     $a3, $a3, $a0
800215ec andi    $v0, $v0, 0xffff
800215f0 or      $a3, $a3, $v0
800215f4 sll     $v0, $a3, 0x10
800215f8 beqz    $v0, 0x80021620
800215fc lui     $v0, 0x800f
80021600 addiu   $v0, $v0, -0x4a78
80021604 lhu     $v1, 2($v0)
80021608 nop     
8002160c or      $v1, $v1, $a3
80021610 sh      $v1, 2($v0)
80021614 lw      $v0, 8($t0)
80021618 nop     
8002161c sw      $v0, 0xc($t0)
80021620 sra     $v1, $a3, 0x10
80021624 andi    $a3, $a3, 0xffff
80021628 nor     $v0, $zero, $a2
8002162c and     $v0, $v0, $v1
80021630 sll     $v0, $v0, 0x10
80021634 or      $a3, $a3, $v0
80021638 sra     $a0, $a3, 0x10
8002163c beqz    $a0, 0x80021660
80021640 lui     $v0, 0x800f
80021644 lhu     $v1, -0x4a78($v0)
80021648 nop     
8002164c or      $v1, $v1, $a0
80021650 sh      $v1, -0x4a78($v0)
80021654 lw      $v0, 0xc($t0)
80021658 nop     
8002165c sw      $v0, 8($t0)
80021660 bnez    $a3, 0x80021af0
80021664 nop     
80021668 lw      $v1, 0xc($t0)
8002166c lw      $v0, 8($t0)
80021670 nop     
80021674 beq     $v1, $v0, 0x80021af0
80021678 addu    $v1, $v0, $v1
8002167c andi    $v0, $v1, 1
80021680 beqz    $v0, 0x80021694
80021684 sw      $v1, 8($t0)
80021688 sra     $v0, $v1, 1
8002168c j       0x8001f1c8
80021690 addiu   $v0, $v0, 1
80021694 sra     $v0, $v1, 1
80021698 sw      $v0, 8($t0)
8002169c lw      $v0, 8($t0)
800216a0 j       0x8001f620
800216a4 sw      $v0, 0xc($t0)
800216a8 addiu   $v0, $zero, 0xa
800216ac bne     $a0, $v0, 0x800216f0
800216b0 lui     $a1, 0x800f
800216b4 lui     $v1, 0x800f
800216b8 addiu   $v0, $zero, -0x4a00
800216bc lui     $a0, 0x800f
800216c0 sh      $v0, -0x4a32($v1)
800216c4 lui     $v1, 0x800f
800216c8 lhu     $v0, -0x4a30($a0)
800216cc lbu     $v1, -0x4a76($v1)
800216d0 ori     $v0, $v0, 0x12  <== ORI 0x12
800216d4 bnez    $v1, 0x80021708
800216d8 sh      $v0, -0x4a30($a0)
800216dc lw      $v0, 0xc($t0)
800216e0 nop     
800216e4 addiu   $v0, $v0, -1
800216e8 j       0x8001f238
800216ec sw      $v0, 0xc($t0)
800216f0 lui     $a0, 0x800f
800216f4 lhu     $v0, -0x4a30($a1)
800216f8 addiu   $v1, $zero, 0x3600
800216fc sh      $v1, -0x4a32($a0)
80021700 ori     $v0, $v0, 0x42  <== ORI 0x42
80021704 sh      $v0, -0x4a30($a1)
80021708 beqz    $a3, 0x8002181c
8002170c nop     
80021710 lw      $a2, 0xc($t0)
80021714 lw      $v0, 8($t0)
80021718 sll     $a2, $a2, 2
8002171c addu    $a2, $a2, $v0
80021720 beqz    $a2, 0x80021af0
80021724 nop     
80021728 bgez    $a2, 0x8002173c
8002172c lui     $v0, 0xffff
80021730 and     $a2, $a2, $v0
80021734 j       0x8001f274
80021738 ori     $a2, $a2, 0xff00
8002173c and     $a2, $a2, $v0
80021740 ori     $a2, $a2, 0xff
80021744 and     $v0, $a3, $a2
80021748 lui     $v1, 0xffff
8002174c and     $a3, $a3, $v1
80021750 andi    $v0, $v0, 0xffff
80021754 or      $a3, $a3, $v0
80021758 sll     $v0, $a3, 0x10
8002175c beqz    $v0, 0x800217c0
80021760 sll     $v0, $a3, 0x18
80021764 beqz    $v0, 0x8002177c
80021768 nor     $a0, $zero, $a3
8002176c lw      $v0, 8($t0)
80021770 nop     
80021774 addiu   $v0, $v0, 3
80021778 sw      $v0, 8($t0)
8002177c and     $a3, $a3, $v1
80021780 andi    $a0, $a0, 0xffff
80021784 lui     $v1, 0x800f
80021788 addiu   $v1, $v1, -0x4a78
8002178c lhu     $v0, 2($v1)
80021790 or      $a3, $a3, $a0
80021794 or      $v0, $v0, $a3
80021798 sh      $v0, 2($v1)
8002179c lw      $v0, 8($t0)
800217a0 nop     
800217a4 sra     $v0, $v0, 2
800217a8 sw      $v0, 8($t0)
800217ac move    $v1, $v0
800217b0 negu    $v0, $v0
800217b4 sll     $v1, $v1, 2
800217b8 sw      $v0, 0xc($t0)
800217bc sw      $v1, 8($t0)
800217c0 sra     $v0, $a3, 0x10
800217c4 andi    $a3, $a3, 0xffff
800217c8 and     $v0, $v0, $a2
800217cc sll     $v0, $v0, 0x10
800217d0 or      $a3, $a3, $v0
800217d4 sra     $v0, $a3, 0x10
800217d8 beqz    $v0, 0x80021814
800217dc nor     $v0, $zero, $v0
800217e0 andi    $a3, $a3, 0xffff
800217e4 sll     $v0, $v0, 0x10
800217e8 or      $a3, $a3, $v0
800217ec lui     $a0, 0x800f
800217f0 lhu     $v0, -0x4a78($a0)
800217f4 sra     $v1, $a3, 0x10
800217f8 or      $v0, $v0, $v1
800217fc sh      $v0, -0x4a78($a0)
80021800 lw      $v0, 0xc($t0)
80021804 nop     
80021808 sll     $v0, $v0, 2
8002180c negu    $v0, $v0
80021810 sw      $v0, 8($t0)
80021814 bnez    $a3, 0x80021af0
80021818 nop     
8002181c lw      $a2, 0xc($t0)
80021820 lw      $v0, 8($t0)
80021824 sll     $a2, $a2, 2
80021828 beq     $a2, $v0, 0x80021af0
8002182c sll     $v0, $v0, 2
80021830 lw      $v1, 0xc($t0)
80021834 sw      $v0, 8($t0)
80021838 subu    $v1, $v1, $v0
8002183c andi    $v0, $v1, 0x10
80021840 beqz    $v0, 0x80021854
80021844 sw      $v1, 0xc($t0)
80021848 sra     $v0, $v1, 4
8002184c j       0x8001f388
80021850 addiu   $v0, $v0, 1
80021854 sra     $v0, $v1, 4
80021858 sw      $v0, 0xc($t0)
8002185c lw      $v0, 0xc($t0)
80021860 nop     
80021864 negu    $v0, $v0
80021868 sll     $v0, $v0, 2
8002186c j       0x8001f620
80021870 sw      $v0, 8($t0)
80021874 addiu   $v0, $zero, 0xb
80021878 bne     $a0, $v0, 0x800218bc
8002187c lui     $a1, 0x800f
80021880 lui     $v1, 0x800f
80021884 addiu   $v0, $zero, -0x6000
80021888 lui     $a0, 0x800f
8002188c sh      $v0, -0x4a32($v1)
80021890 lui     $v1, 0x800f
80021894 lhu     $v0, -0x4a30($a0)
80021898 lbu     $v1, -0x4a76($v1)
8002189c ori     $v0, $v0, 0x12  <== ORI 0x12
800218a0 beqz    $v1, 0x800218d4
800218a4 sh      $v0, -0x4a30($a0)
800218a8 lw      $v0, 0xc($t0)
800218ac nop     
800218b0 addiu   $v0, $v0, -1
800218b4 j       0x8001f404
800218b8 sw      $v0, 0xc($t0)
800218bc lui     $a0, 0x800f
800218c0 lhu     $v0, -0x4a30($a1)
800218c4 addiu   $v1, $zero, 0x2000
800218c8 sh      $v1, -0x4a32($a0)
800218cc ori     $v0, $v0, 0x42  <== ORI 0x42
800218d0 sh      $v0, -0x4a30($a1)
800218d4 beqz    $a3, 0x800219b8
800218d8 nop     
800218dc lw      $a2, 8($t0)
800218e0 lw      $v0, 0xc($t0)
800218e4 nop     
800218e8 addu    $a2, $a2, $v0
800218ec beqz    $a2, 0x80021af0
800218f0 nop     
800218f4 bgez    $a2, 0x80021908
800218f8 lui     $v0, 0xffff
800218fc and     $a2, $a2, $v0
80021900 j       0x8001f440
80021904 ori     $a2, $a2, 0xff00
80021908 and     $a2, $a2, $v0
8002190c ori     $a2, $a2, 0xff
80021910 and     $v0, $a3, $a2
80021914 lui     $v1, 0xffff
80021918 and     $a3, $a3, $v1
8002191c andi    $v0, $v0, 0xffff
80021920 or      $a3, $a3, $v0
80021924 sll     $v0, $a3, 0x10
80021928 beqz    $v0, 0x80021960
8002192c nor     $a0, $zero, $a3
80021930 and     $a3, $a3, $v1
80021934 andi    $a0, $a0, 0xffff
80021938 lui     $v1, 0x800f
8002193c addiu   $v1, $v1, -0x4a78
80021940 lhu     $v0, 2($v1)
80021944 or      $a3, $a3, $a0
80021948 or      $v0, $v0, $a3
8002194c sh      $v0, 2($v1)
80021950 lw      $v0, 8($t0)
80021954 nop     
80021958 negu    $v0, $v0
8002195c sw      $v0, 0xc($t0)
80021960 sra     $v0, $a3, 0x10
80021964 andi    $a3, $a3, 0xffff
80021968 and     $v0, $v0, $a2
8002196c sll     $v0, $v0, 0x10
80021970 or      $a3, $a3, $v0
80021974 sra     $v0, $a3, 0x10
80021978 beqz    $v0, 0x800219b0
8002197c nor     $v0, $zero, $v0
80021980 andi    $a3, $a3, 0xffff
80021984 sll     $v0, $v0, 0x10
80021988 or      $a3, $a3, $v0
8002198c lui     $a0, 0x800f
80021990 lhu     $v0, -0x4a78($a0)
80021994 sra     $v1, $a3, 0x10
80021998 or      $v0, $v0, $v1
8002199c sh      $v0, -0x4a78($a0)
800219a0 lw      $v0, 0xc($t0)
800219a4 nop     
800219a8 negu    $v0, $v0
800219ac sw      $v0, 8($t0)
800219b0 bnez    $a3, 0x80021af0
800219b4 nop     
800219b8 lw      $a2, 8($t0)
800219bc lw      $v0, 0xc($t0)
800219c0 move    $v1, $a2
800219c4 addu    $a2, $a2, $v0
800219c8 beqz    $a2, 0x80021af0
800219cc subu    $v1, $v0, $v1
800219d0 andi    $v0, $v1, 1
800219d4 beqz    $v0, 0x800219f0
800219d8 sw      $v1, 0xc($t0)
800219dc srl     $v0, $v1, 0x1f
800219e0 addu    $v0, $v1, $v0
800219e4 sra     $v0, $v0, 1
800219e8 j       0x8001f52c
800219ec addiu   $v0, $v0, 1
800219f0 srl     $v0, $v1, 0x1f
800219f4 addu    $v0, $v1, $v0
800219f8 sra     $v0, $v0, 1
800219fc sw      $v0, 0xc($t0)
80021a00 lw      $v0, 0xc($t0)
80021a04 nop     
80021a08 negu    $v0, $v0
80021a0c j       0x8001f620
80021a10 sw      $v0, 8($t0)
80021a14 lui     $v1, 0x800f
80021a18 addiu   $v0, $zero, 0x4000
80021a1c lui     $a1, 0x800f
80021a20 lui     $a0, 0x800f
80021a24 sh      $v0, -0x4a32($v1)
80021a28 lhu     $v1, -0x4a30($a1)
80021a2c addiu   $v0, $zero, 0xff
80021a30 sb      $v0, -0x4a76($a0)
80021a34 sw      $zero, 0xc($t0)
80021a38 j       0x8001f61c
80021a3c ori     $v1, $v1, 0x42  <== ORI 0x42
80021a40 lui     $v1, 0x800f
80021a44 addiu   $v0, $zero, -0x4000
80021a48 lui     $a1, 0x800f
80021a4c lui     $a0, 0x800f
80021a50 sh      $v0, -0x4a32($v1)
80021a54 lhu     $v1, -0x4a30($a1)
80021a58 addiu   $v0, $zero, 0xff
80021a5c sb      $v0, -0x4a75($a0)
80021a60 sw      $zero, 0xc($t0)
80021a64 j       0x8001f61c
80021a68 ori     $v1, $v1, 0x12  <== ORI 0x12
80021a6c addiu   $v0, $zero, 7
80021a70 bne     $a0, $v0, 0x80021a94
80021a74 andi    $v1, $a0, 0xff
80021a78 lw      $v0, 8($t0)
80021a7c nop     
80021a80 bgtz    $v0, 0x80021a90
80021a84 addiu   $a0, $zero, 0xd
80021a88 bgez    $v0, 0x80021af0
80021a8c addiu   $a0, $zero, 0xc
80021a90 andi    $v1, $a0, 0xff
80021a94 addiu   $v0, $zero, 0xd
80021a98 bne     $v1, $v0, 0x80021ac4
80021a9c addiu   $v0, $zero, 0xc
80021aa0 lui     $v1, 0x800f
80021aa4 addiu   $v0, $zero, -0x8000
80021aa8 lui     $a1, 0x800f
80021aac lui     $a0, 0x800f
80021ab0 sh      $v0, -0x4a32($v1)
80021ab4 lhu     $v1, -0x4a30($a1)
80021ab8 addiu   $v0, $zero, 0xff
80021abc j       0x8001f614
80021ac0 sb      $v0, -0x4a77($a0)
80021ac4 bne     $v1, $v0, 0x80021af0
80021ac8 lui     $v0, 0x800f
80021acc lui     $a1, 0x800f
80021ad0 lhu     $v1, -0x4a30($a1)
80021ad4 lui     $a0, 0x800f
80021ad8 sh      $zero, -0x4a32($v0)
80021adc addiu   $v0, $zero, 0xff
80021ae0 sb      $v0, -0x4a78($a0)
80021ae4 sw      $zero, 8($t0)
80021ae8 ori     $v1, $v1, 6
80021aec sh      $v1, -0x4a30($a1)
80021af0 jr      $ra
80021af4 addiu   $sp, $sp, 0x28
80021af8 addiu   $sp, $sp, -0x18
80021afc sll     $a1, $a1, 0x10
80021b00 sra     $a1, $a1, 0x10
80021b04 addiu   $v0, $zero, 0xf
80021b08 bne     $a1, $v0, 0x80021b28
80021b0c sw      $ra, 0x10($sp)
80021b10 lw      $v0, 0xc($a0)
80021b14 nop     
80021b18 bgtz    $v0, 0x80021b28
80021b1c addiu   $a1, $zero, 0xd
80021b20 bgez    $v0, 0x80021b30
80021b24 addiu   $a1, $zero, 0xb
80021b28 jal     0x8001ed88
80021b2c nop     
80021b30 lw      $ra, 0x10($sp)
80021b34 nop     
80021b38 jr      $ra
80021b3c addiu   $sp, $sp, 0x18