; pow_add (xref site 0x80047a1c, func start 0x800479f8)  (start 0x800479f8, 768 bytes)
800479F8: addiu    $sp, $sp, 0x20
800479FC: lui      $v0, 0x800d
80047A00: lw       $v0, -0x6568($v0)
80047A04: addiu    $sp, $sp, -0x38
80047A08: sw       $ra, 0x30($sp)
80047A0C: lh       $v0, 0xcc($v0)
80047A10: nop      
80047A14: bnez     $v0, 0x80047a2c
80047A18: lui      $v0, 0x8008
80047A1C: lui      $v0, 0x8008
80047A20: lhu      $a3, 0x7a78($v0)
80047A24: j        0x80047a38
80047A28: sll      $v0, $a3, 0x10
80047A2C: lhu      $a3, 0x7a7c($v0)
80047A30: nop      
80047A34: sll      $v0, $a3, 0x10
80047A38: sra      $v0, $v0, 0x10
80047A3C: beqz     $v0, 0x80047ae4
80047A40: slti     $v0, $v0, 0xf
80047A44: bnez     $v0, 0x80047a54
80047A48: sll      $v0, $a3, 0x10
80047A4C: addiu    $a3, $zero, 0xe
80047A50: sll      $v0, $a3, 0x10
80047A54: sra      $v0, $v0, 0x10
80047A58: blez     $v0, 0x80047a84
80047A5C: move     $v1, $zero
80047A60: addiu    $a1, $sp, 0x20
80047A64: addiu    $a2, $zero, 0xb
80047A68: move     $a0, $v0
80047A6C: addu     $v0, $a1, $v1
80047A70: sb       $a2, ($v0)
80047A74: addiu    $v1, $v1, 1
80047A78: slt      $v0, $v1, $a0
80047A7C: bnez     $v0, 0x80047a70
80047A80: addu     $v0, $a1, $v1
80047A84: lui      $v0, 0x800d
80047A88: lw       $v0, -0x6568($v0)
80047A8C: nop      
80047A90: lw       $v1, 0xd4($v0)
80047A94: lh       $v0, 0xcc($v0)
80047A98: lhu      $a1, 0x1c($v1)
80047A9C: beqz     $v0, 0x80047aac
80047AA0: sll      $v0, $a3, 0x10
80047AA4: sra      $v0, $v0, 0xd
80047AA8: subu     $a1, $a1, $v0
80047AAC: lh       $a2, 0x1e($v1)
80047AB0: addiu    $v0, $zero, 1
80047AB4: sw       $v0, 0x10($sp)
80047AB8: addiu    $v0, $zero, 2
80047ABC: sw       $v0, 0x14($sp)
80047AC0: ori      $v0, $zero, 0xffff
80047AC4: sll      $a1, $a1, 0x10
80047AC8: sll      $a3, $a3, 0x10
80047ACC: addiu    $a0, $sp, 0x20
80047AD0: sra      $a1, $a1, 0x10
80047AD4: sra      $a3, $a3, 0x10
80047AD8: sw       $zero, 0x18($sp)
80047ADC: jal      0x80019a0c
80047AE0: sw       $v0, 0x1c($sp)
80047AE4: lw       $ra, 0x30($sp)
80047AE8: nop      
80047AEC: jr       $ra
80047AF0: addiu    $sp, $sp, 0x38
80047AF4: addiu    $sp, $sp, -0x20
80047AF8: sw       $s1, 0x14($sp)
80047AFC: lui      $s1, 0x800d
80047B00: lw       $v0, -0x6568($s1)
80047B04: sw       $ra, 0x18($sp)
80047B08: sw       $s0, 0x10($sp)
80047B0C: lh       $s0, 0xcc($v0)
80047B10: jal      0x8003a438
80047B14: move     $a0, $s0
80047B18: jal      0x80027d38
80047B1C: nop      
80047B20: lui      $v0, 0x800d
80047B24: addiu    $v0, $v0, 0x4a22
80047B28: addu     $s0, $s0, $v0
80047B2C: addiu    $v0, $zero, 2
80047B30: sb       $v0, ($s0)
80047B34: lui      $v0, 0x8004
80047B38: lw       $v1, -0x6568($s1)
80047B3C: addiu    $v0, $v0, 0x7b5c
80047B40: jal      0x80047b5c
80047B44: sw       $v0, ($v1)
80047B48: lw       $ra, 0x18($sp)
80047B4C: lw       $s1, 0x14($sp)
80047B50: lw       $s0, 0x10($sp)
80047B54: jr       $ra
80047B58: addiu    $sp, $sp, 0x20
80047B5C: addiu    $sp, $sp, -0x48
80047B60: sw       $s3, 0x3c($sp)
80047B64: lui      $s3, 0x800d
80047B68: lui      $a0, 0x800f
80047B6C: lw       $v0, -0x6568($s3)
80047B70: lbu      $v1, -0x22b4($a0)
80047B74: sw       $ra, 0x44($sp)
80047B78: sw       $s4, 0x40($sp)
80047B7C: sw       $s2, 0x38($sp)
80047B80: sw       $s1, 0x34($sp)
80047B84: sw       $s0, 0x30($sp)
80047B88: lh       $s0, 0xcc($v0)
80047B8C: nop      
80047B90: srav     $v0, $v1, $s0
80047B94: andi     $v0, $v0, 1
80047B98: beqz     $v0, 0x80047bcc
80047B9C: addiu    $v0, $zero, 1
80047BA0: sllv     $v0, $v0, $s0
80047BA4: nor      $v0, $zero, $v0
80047BA8: and      $v0, $v1, $v0
80047BAC: sb       $v0, -0x22b4($a0)
80047BB0: lui      $a0, 0x8004
80047BB4: addiu    $a0, $a0, 0x5908
80047BB8: lui      $a1, 0x8004
80047BBC: jal      0x800152ac
80047BC0: addiu    $a1, $a1, 0x7b5c
80047BC4: j        0x80047d38
80047BC8: nop      
80047BCC: lui      $v0, 0x800d
80047BD0: addiu    $v0, $v0, 0x4a22
80047BD4: addu     $v0, $s0, $v0
80047BD8: lbu      $v1, ($v0)
80047BDC: addiu    $v0, $zero, 1
80047BE0: bne      $v1, $v0, 0x80047c64
80047BE4: lui      $a1, 0x6666
80047BE8: lui      $v0, 0x800f
80047BEC: addiu    $v0, $v0, -0x1ce8
80047BF0: sll      $v1, $s0, 3
80047BF4: addu     $a2, $v1, $v0
80047BF8: lw       $a0, ($a2)
80047BFC: ori      $a1, $a1, 0x6667
80047C00: mult     $a0, $a1
80047C04: sra      $v0, $a0, 0x1f
80047C08: mfhi     $t0
80047C0C: sra      $v1, $t0, 2
80047C10: subu     $v1, $v1, $v0
80047C14: sll      $v0, $v1, 2
80047C18: addu     $v0, $v0, $v1
80047C1C: sll      $v0, $v0, 1
80047C20: subu     $a0, $a0, $v0
80047C24: slti     $a0, $a0, 9
80047C28: beqz     $a0, 0x80047c40
80047C2C: nop      
80047C30: lw       $v0, ($a2)
80047C34: nop      
80047C38: addiu    $v0, $v0, 1
80047C3C: sw       $v0, ($a2)
80047C40: jal      0x80045158
80047C44: move     $a0, $s0
80047C48: lui      $v0, 0x8004
80047C4C: lw       $v1, -0x6568($s3)
80047C50: addiu    $v0, $v0, 0x6efc
80047C54: jal      0x80046efc
80047C58: sw       $v0, ($v1)
80047C5C: j        0x80047d38
80047C60: nop      
80047C64: jal      0x80027d54
80047C68: nop      
80047C6C: sll      $a2, $v0, 0x10
80047C70: bnez     $a2, 0x80047c88
80047C74: lui      $v0, 0x800d
80047C78: jal      0x80047d58
80047C7C: nop      
80047C80: j        0x80047d38
80047C84: nop      
80047C88: lbu      $v0, 0x4a44($v0)
80047C8C: nop      
80047C90: srav     $v0, $v0, $s0
80047C94: andi     $v0, $v0, 1
80047C98: bnez     $v0, 0x80047cb0
80047C9C: lui      $s4, 0x800f
80047CA0: jal      0x8004820c
80047CA4: nop      
80047CA8: j        0x80047d38
80047CAC: nop      
80047CB0: lbu      $v0, -0x22b9($s4)
80047CB4: nop      
80047CB8: beqz     $v0, 0x80047d1c
80047CBC: addiu    $a0, $sp, 0x20
80047CC0: lui      $a1, 0x8001
80047CC4: addiu    $a1, $a1, 0x1228
80047CC8: sra      $a2, $a2, 0x18
80047CCC: lw       $v0, -0x6568($s3)
80047CD0: sltu     $s0, $zero, $s0
80047CD4: lw       $v0, 0xd4($v0)
80047CD8: nop      
80047CDC: lhu      $s1, 0x20($v0)
80047CE0: lhu      $s2, 0x22($v0)
80047CE4: jal      0x8007e8b4
80047CE8: sll      $s0, $s0, 1
80047CEC: addiu    $a0, $sp, 0x20
80047CF0: move     $a2, $s0
80047CF4: addiu    $v0, $zero, 0x100