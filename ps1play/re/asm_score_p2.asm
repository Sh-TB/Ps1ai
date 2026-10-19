; score_p2 (xref site 0x80052654, func start 0x8005263c)  (start 0x8005263c, 768 bytes)
8005263C: addiu    $sp, $sp, 0x18
80052640: andi     $a0, $a0, 1
80052644: beqz     $a0, 0x80052654
80052648: lui      $v0, 0x800f
8005264C: j        0x8005265c
80052650: addiu    $a2, $v0, -0x1ce8
80052654: lui      $v0, 0x800f
80052658: addiu    $a2, $v0, -0x1ce0
8005265C: lui      $v0, 0x5f5
80052660: lw       $v1, ($a2)
80052664: ori      $v0, $v0, 0xe0ff
80052668: addu     $a1, $v1, $a1
8005266C: slt      $v0, $v0, $a1
80052670: beqz     $v0, 0x800526bc
80052674: sw       $a1, ($a2)
80052678: lui      $v0, 0x51eb
8005267C: ori      $v0, $v0, 0x851f
80052680: mult     $a1, $v0
80052684: lui      $a0, 0x5f5
80052688: ori      $a0, $a0, 0xe09c
8005268C: sra      $v0, $a1, 0x1f
80052690: mfhi     $a3
80052694: sra      $v1, $a3, 5
80052698: subu     $v1, $v1, $v0
8005269C: sll      $v0, $v1, 1
800526A0: addu     $v0, $v0, $v1
800526A4: sll      $v0, $v0, 3
800526A8: addu     $v0, $v0, $v1
800526AC: sll      $v0, $v0, 2
800526B0: subu     $v0, $a1, $v0
800526B4: addu     $v0, $v0, $a0
800526B8: sw       $v0, ($a2)
800526BC: jr       $ra
800526C0: nop      
800526C4: addiu    $sp, $sp, -0x28
800526C8: sw       $s0, 0x20($sp)
800526CC: move     $s0, $a0
800526D0: addiu    $a0, $sp, 0x10
800526D4: lui      $v0, 0x8001
800526D8: sw       $ra, 0x24($sp)
800526DC: lw       $a2, ($a1)
800526E0: jal      0x8007e8b4
800526E4: addiu    $a1, $v0, 0x1354
800526E8: jal      0x8007e7d4
800526EC: addiu    $a0, $sp, 0x10
800526F0: move     $a3, $v0
800526F4: andi     $v0, $s0, 1
800526F8: beqz     $v0, 0x80052760
800526FC: lui      $v0, 0x5f5
80052700: lui      $a2, 0x800f
80052704: lw       $v1, -0x1ce8($a2)
80052708: ori      $v0, $v0, 0xe0ff
8005270C: addu     $a1, $v1, $a3
80052710: slt      $v0, $v0, $a1
80052714: beqz     $v0, 0x80052760
80052718: sw       $a1, -0x1ce8($a2)
8005271C: lui      $v0, 0x51eb
80052720: ori      $v0, $v0, 0x851f
80052724: mult     $a1, $v0
80052728: lui      $a0, 0x5f5
8005272C: ori      $a0, $a0, 0xe09c
80052730: sra      $v0, $a1, 0x1f
80052734: mfhi     $t0
80052738: sra      $v1, $t0, 5
8005273C: subu     $v1, $v1, $v0
80052740: sll      $v0, $v1, 1
80052744: addu     $v0, $v0, $v1
80052748: sll      $v0, $v0, 3
8005274C: addu     $v0, $v0, $v1
80052750: sll      $v0, $v0, 2
80052754: subu     $v0, $a1, $v0
80052758: addu     $v0, $v0, $a0
8005275C: sw       $v0, -0x1ce8($a2)
80052760: andi     $v0, $s0, 2
80052764: beqz     $v0, 0x800527d0
80052768: lui      $v0, 0x5f5
8005276C: lui      $v1, 0x800f
80052770: addiu    $a2, $v1, -0x1ce8
80052774: lw       $v1, 8($a2)
80052778: ori      $v0, $v0, 0xe0ff
8005277C: addu     $a1, $v1, $a3
80052780: slt      $v0, $v0, $a1
80052784: beqz     $v0, 0x800527d0
80052788: sw       $a1, 8($a2)
8005278C: lui      $v0, 0x51eb
80052790: ori      $v0, $v0, 0x851f
80052794: mult     $a1, $v0
80052798: lui      $a0, 0x5f5
8005279C: ori      $a0, $a0, 0xe09c
800527A0: sra      $v0, $a1, 0x1f
800527A4: mfhi     $t0
800527A8: sra      $v1, $t0, 5
800527AC: subu     $v1, $v1, $v0
800527B0: sll      $v0, $v1, 1
800527B4: addu     $v0, $v0, $v1
800527B8: sll      $v0, $v0, 3
800527BC: addu     $v0, $v0, $v1
800527C0: sll      $v0, $v0, 2
800527C4: subu     $v0, $a1, $v0
800527C8: addu     $v0, $v0, $a0
800527CC: sw       $v0, 8($a2)
800527D0: lw       $ra, 0x24($sp)
800527D4: lw       $s0, 0x20($sp)
800527D8: jr       $ra
800527DC: addiu    $sp, $sp, 0x28
800527E0: addiu    $sp, $sp, -0x20
800527E4: sw       $ra, 0x18($sp)
800527E8: lh       $v0, ($a1)
800527EC: addiu    $a1, $sp, 0x10
800527F0: jal      0x800526c4
800527F4: sw       $v0, 0x10($sp)
800527F8: lw       $ra, 0x18($sp)
800527FC: nop      
80052800: jr       $ra
80052804: addiu    $sp, $sp, 0x20
80052808: andi     $v0, $a0, 1
8005280C: beqz     $v0, 0x80052818
80052810: lui      $v0, 0x800f
80052814: sw       $zero, -0x1ce8($v0)
80052818: andi     $v0, $a0, 2
8005281C: beqz     $v0, 0x80052828
80052820: lui      $v0, 0x800f
80052824: sw       $zero, -0x1ce0($v0)
80052828: jr       $ra
8005282C: nop      
80052830: blez     $a1, 0x80052858
80052834: andi     $v0, $a0, 0x8000
80052838: beqz     $v0, 0x80052848
8005283C: sll      $v0, $a0, 1
80052840: j        0x8005284c
80052844: ori      $a0, $v0, 1
80052848: sll      $a0, $a0, 1
8005284C: addiu    $a1, $a1, -1
80052850: bgtz     $a1, 0x80052838
80052854: andi     $v0, $a0, 0x8000
80052858: jr       $ra
8005285C: andi     $v0, $a0, 0xffff
80052860: addiu    $sp, $sp, -0x30
80052864: sw       $s0, 0x10($sp)
80052868: move     $s0, $a0
8005286C: andi     $v0, $s0, 0xffff
80052870: sw       $ra, 0x28($sp)
80052874: sw       $s5, 0x24($sp)
80052878: sw       $s4, 0x20($sp)
8005287C: sw       $s3, 0x1c($sp)
80052880: sw       $s2, 0x18($sp)
80052884: beqz     $v0, 0x800528a4
80052888: sw       $s1, 0x14($sp)
8005288C: lui      $v1, 0x800f
80052890: lhu      $s0, -0x1cd8($v1)
80052894: nop      
80052898: addiu    $v0, $s0, 1
8005289C: move     $s0, $v0
800528A0: sh       $v0, -0x1cd8($v1)
800528A4: lui      $v0, 0x800f
800528A8: addiu    $s2, $v0, -0x1cd0
800528AC: move     $s4, $s0
800528B0: move     $s3, $s0
800528B4: move     $s5, $zero
800528B8: sh       $s0, ($s2)
800528BC: addiu    $s2, $s2, 2
800528C0: andi     $s1, $s0, 0xffff
800528C4: sll      $s1, $s1, 1
800528C8: addiu    $a0, $s4, 0x22b7
800528CC: ori      $v0, $zero, 0xffff
800528D0: sltu     $v0, $v0, $s1
800528D4: beqz     $v0, 0x800528e0
800528D8: addiu    $s3, $s3, 0x4555
800528DC: nor      $s1, $zero, $s1
800528E0: xor      $s0, $a0, $s1
800528E4: move     $s4, $s0
800528E8: andi     $a0, $s4, 0xffff
800528EC: jal      0x80052830
800528F0: addiu    $a1, $zero, 1
800528F4: xor      $s0, $s3, $s0
800528F8: move     $s3, $s0
800528FC: andi     $a0, $s3, 0xffff
80052900: jal      0x80052830
80052904: addiu    $a1, $zero, 1
80052908: xor      $s0, $s1, $s0
8005290C: andi     $a0, $s0, 0xffff
80052910: jal      0x80052830
80052914: addiu    $a1, $zero, 1
80052918: addiu    $s5, $s5, 1
8005291C: andi     $v0, $s5, 0xffff
80052920: sltiu    $v0, $v0, 0x37
80052924: bnez     $v0, 0x800528b8
80052928: lui      $v0, 0x800f
8005292C: addiu    $s2, $s2, -2
80052930: lw       $ra, 0x28($sp)
80052934: lw       $s5, 0x24($sp)
80052938: lw       $s4, 0x20($sp)