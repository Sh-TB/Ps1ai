.set noat
.set noreorder
.text

.global FUN_80022500
FUN_80022500:
  addiu $sp, $sp, -0x50
  sw $s3, 0x34($sp)
  sw $s1, 0x2c($sp)
  move $s1, $a1
  lui $v1, 0xff
  sw $ra, 0x4c($sp)
  sw $fp, 0x48($sp)
  sw $s7, 0x44($sp)
  sw $s6, 0x40($sp)
  sw $s5, 0x3c($sp)
  sw $s4, 0x38($sp)
  sw $s2, 0x30($sp)
  sw $s0, 0x28($sp)
  sw $a2, 0x58($sp)
  sw $a3, 0x5c($sp)
  lw $v0, 8($s1)
  ori $v1, $v1, 0xffff
  slt $v0, $v1, $v0
  beqz $v0, .L80022554
  move $s3, $a0
  sw $v1, 8($s1)
.L80022554:
  lw $v0, 0xc($s1)
  nop 
  slt $v0, $v1, $v0
  beqz $v0, .L8002256c
  nop 
  sw $v1, 0xc($s1)
.L8002256c:
  lui $v1, 0xff00
  lw $v0, 8($s1)
  ori $v1, $v1, 1
  slt $v0, $v0, $v1
  beqz $v0, .L80022588
  nop 
  sw $v1, 8($s1)
.L80022588:
  lw $v0, 0xc($s1)
  nop 
  slt $v0, $v0, $v1
  beqz $v0, .L800225a0
  nop 
  sw $v1, 0xc($s1)
.L800225a0:
  lui $v1, 0x800f
  lui $v0, 0x800f
  move $s4, $v0
  lui $s7, 0x800f
  addiu $fp, $s7, -0x4a50
  lui $t0, 0x800f
  addiu $s6, $t0, -0x4a68
  move $t0, $v1
  addiu $t0, $t0, -0x4a78
  sb $zero, 1($t0)
  sb $zero, -0x4a78($v1)
  addiu $v1, $zero, -1
  sb $zero, 3($t0)
  sb $zero, 2($t0)
  lui $t0, 0x800f
  lui $v0, 0x800f
  sw $v1, -0x4a48($v0)
  lui $v0, 0x800f
  sw $v1, -0x4a58($t0)
  lui $v1, 0x800f
  sw $zero, -0x4a14($v0)
  lui $v0, 0x8000
  sw $v0, -0x4a2c($v1)
  lui $v0, 0x800f
  .byte 0x58, 0x58, 0xbd, 0x69
  .byte 0x98, 0xde, 0xb6, 0x60
  bne $s4, $k1, 0x8002e6b0
  jalx 0x8027ced4
  sb $t5, 0x79c5($t4)
  beql $s7, $a0, 0x8001ebf0
  .byte 0x6b, 0x73, 0x83, 0x3f
  swl $sp, -0x7009($ra)
  swr $t9, -0x7e03($t3)
  lwc2 $28, 0x47c2($a0)
  lbu $a1, 0x48df($t6)
  ori $v0, $fp, 0x7f77
  .byte 0x2d, 0xff, 0x5a, 0x64
  sc $zero, -0x3f2f($s4)
  sdc2 $20, -0x1f9e($t1)
  .byte 0x76, 0xf5, 0x80, 0xd2
  .byte 0xce, 0xd2, 0x44, 0x6a
  .byte 0xe4, 0x97, 0x62, 0x4a
  addi $t1, $zero, -0x452d
  .byte 0x54, 0x5d, 0xad, 0xd1
  .byte 0x1d, 0xf6, 0xad, 0x49
  swl $s4, 0x4601($k1)
  bnel $t3, $s3, 0x8003bc68
  .byte 0xfb, 0x62, 0x48, 0x3f
  jal 0x80d03778
  .byte 0xaa, 0x5e, 0xb4, 0x5a
  ld.b $w23, -0x57($t1)
  ldc1 $f7, 0x578e($s3)
  .byte 0x6e, 0xc7, 0x0b, 0x4f
  j 0x8e00685c
  lwc2 $15, 0xb6e($t4)
  bnel $ra, $zero, 0x8003d5c0
  .byte 0xae, 0x48, 0xb8, 0x7c
  .byte 0xc7, 0xa5, 0xfc, 0x44
  lh $t4, -0x69e9($t0)
  sdc1 $f2, -0x6c2($t6)
  cache 0x1c, -0x50f5($gp)
  bne $t8, $t1, 0x80007ce0
  .byte 0x80, 0x0e, 0x67, 0xed
  ldc2 $26, 0x6272($s3)
  tlti $a1, 0x664d
  .byte 0x90, 0x9f, 0x45, 0xb4
  lh $k0, -0x6f67($s1)
  addi $t7, $s4, 0x43f1
  slti $t0, $a3, 0x2553
  .byte 0x9c, 0x16, 0xaf, 0xb5
  sw $gp, -0x5dec($zero)
  sc $s3, 0x4893($fp)
  .byte 0x60, 0xb9, 0xad, 0xf0
  lwr $t5, -0x74b5($t4)
  swc1 $f11, -0xebb($k1)
  ll $at, -0x621c($t3)
  .byte 0x83, 0x1f, 0x7f, 0x7b
  .byte 0xb6, 0x83, 0x0d, 0x43
  lwr $s0, -0x4d4a($t6)
  j 0x8c65f394
  .byte 0xb3, 0xbc, 0x0e, 0x5e
  sdc1 $f27, 0x5989($ra)
  .byte 0x06, 0x3d, 0x1d, 0x46
  sdc1 $f1, 0x1f4c($t8)
  .byte 0xd4, 0x00, 0x11, 0x00
  lw $k1, -0x6f2f($sp)
  .byte 0x95, 0x3a, 0xc1, 0x7d
  st.w $w9, -0x2ac($at)
  bnel $t9, $s3, 0x800176d8
  .byte 0xe7, 0xe4, 0xdf, 0x1e
  sc $sp, -0x3416($s2)
  .byte 0x31, 0xe7, 0xe7, 0x5f
  j 0x8de981a8
  lbu $t5, 0x1ae($t6)
  .byte 0x00, 0xff, 0xff, 0xff
  .byte 0xff, 0xff, 0xff, 0xff
  .byte 0xff, 0xff, 0xff, 0x00
  .byte 0x00, 0x35, 0x12, 0x02
  sll $zero, $t0, 0
  sll $zero, $t0, 0
  sh $zero, -0x4a30($s4)
  sw $zero, -0x4a0c($v0)
.L80022738:
  move $a0, $s3
  move $a1, $zero
  jal 0x80024488
  move $a2, $s1
  move $s3, $zero
  move $a0, $s1
  lw $v0, ($s1)
  lui $v1, 0x800f
  sw $v0, -0x4a70($v1)
  lw $v0, 4($s1)
  addiu $v1, $v1, -0x4a70
  jal 0x8001e3b4
  sw $v0, 4($v1)
  beqz $v0, .L80022840
  lui $v0, 0x800f
  lhu $v0, -0x4a78($v0)
  ori $t0, $zero, 0xffff
  beq $v0, $t0, .L800227d0
  lui $t0, 0x800f
  addiu $t0, $t0, -0x4a78
  lhu $v0, 2($t0)
  ori $t0, $zero, 0xffff
  beq $v0, $t0, .L800227d0
  lui $t0, 0x800f
  lw $v1, -0x4a58($t0)
  nop 
  bnez $v1, .L80022810
  addiu $v0, $zero, -1
  lw $v1, 8($s1)
  lw $v0, -0x4a50($s7)
  nop 
  bne $v1, $v0, .L800227e4
  nop 
  lw $v1, 0xc($s1)
  lw $v0, 4($fp)
  nop 
  bne $v1, $v0, .L800227e4
  nop 
.L800227d0:
  lhu $v0, -0x4a30($s4)
  nop 
  ori $v0, $v0, 0x80
  j 0x80020434
  sh $v0, -0x4a30($s4)
.L800227e4:
  lw $v0, 8($s1)
  nop 
  sw $v0, -0x4a50($s7)
  lw $v0, 0xc($s1)
  j 0x80020104
  sw $v0, 4($fp)
.L800227fc:
  lhu $v0, -0x4a30($s4)
  nop 
  ori $v0, $v0, 0x80
  j 0x8002042c
  sh $v0, -0x4a30($s4)
.L80022810:
  bne $v1, $v0, .L80022838
  lui $v1, 0x800f
  lw $v0, 8($s1)
  nop 
  sw $v0, -0x4a50($s7)
  lw $v0, 0xc($s1)
  lui $t0, 0x800f
  sw $zero, -0x4a58($t0)
  sw $v0, 4($fp)
  lui $v1, 0x800f
.L80022838:
  addiu $v0, $zero, -1
  sw $v0, -0x4a48($v1)
.L80022840:
  move $a0, $s3
  jal 0x8001e100
  move $a1, $s1
  move $a0, $s3
  jal 0x8001e340
  move $a1, $s1
  move $s0, $v0
  beqz $s0, .L80022b68
  lui $v0, 0x800f
  lui $s5, 0x800f
  move $a0, $s3
.L8002286c:
  move $a1, $s0
  jal 0x80024488
  move $a2, $s1
  lui $v0, 0x800f
  lw $v0, -0x4a48($v0)
  move $s3, $s0
  beq $v0, $s3, .L80022b44
  lui $t0, 0x800f
  lw $v0, ($s1)
  nop 
  sw $v0, -0x4a68($t0)
  lw $v0, 4($s1)
  nop 
  sw $v0, 4($s6)
  lw $v0, 8($s1)
  move $a0, $s3
  sw $v0, 8($s6)
  lw $v0, 0xc($s1)
  move $a1, $s1
  jal 0x8001fd14
  sw $v0, 0xc($s6)
  lui $v0, 0x800f
  lbu $v0, -0x4a04($v0)
  nop 
  bnez $v0, .L800228f4
  addiu $v0, $zero, -1
  lw $v0, 8($s6)
  nop 
  sw $v0, 8($s1)
  lw $v0, 0xc($s6)
  nop 
  addiu $v0, $v0, -1
  j 0x800201d8
  sw $v0, 0xc($s1)
.L800228f4:
  lhu $v1, -0x4a30($s4)
  sw $zero, 8($s1)
  andi $v1, $v1, 0x20
  bnez $v1, .L80022980
  sw $v0, 0xc($s1)
  lui $v0, 0x800f
  lui $v1, 0x800f
  lhu $v0, -0x4a3a($v0)
  lhu $v1, -0x4a38($v1)
  sll $s2, $v0, 0x10
  or $s2, $s2, $v1
  sll $v0, $s2, 0x10
  beqz $v0, .L80022980
  addiu $a0, $sp, 0x10
  lw $a1, 8($s1)
  lw $a2, 0xc($s1)
  jal 0x8001eba0
  move $a3, $s2
  addiu $a0, $sp, 0x14
  lh $a2, 0x10($sp)
  lw $s2, 0x10($sp)
  jal 0x8001e8e8
  move $a1, $s1
  lw $v1, 0x14($sp)
  lui $v0, 0x8000
  sltu $v0, $v0, $v1
  beqz $v0, .L80022984
  addiu $a0, $sp, 0x18
  lw $v0, -0x4a2c($s5)
  nop 
  slt $v0, $v1, $v0
  bnez $v0, .L80022a24
  lui $v0, 0x800f
  j 0x800202e8
  sw $s2, -0x4a0c($v0)
.L80022980:
  addiu $a0, $sp, 0x18
.L80022984:
  move $a1, $s3
  lhu $a3, 6($s1)
  lh $a2, 2($s1)
  addiu $a3, $a3, -8
  sll $a3, $a3, 0x10
  jal 0x8001e1d4
  sra $a3, $a3, 0x10
  lh $a0, 0x18($sp)
  lw $s0, 0x18($sp)
  beqz $a0, .L80022a24
  lui $v0, 0x800f
  lhu $v1, -0x4a38($v0)
  addiu $v0, $zero, 0xf
  bne $v1, $v0, .L800229c8
  nop 
  beq $a0, $v1, .L80022a24
  nop 
.L800229c8:
  addiu $a0, $sp, 0x1c
  lw $a1, 8($s1)
  lw $a2, 0xc($s1)
  jal 0x8001eba0
  move $a3, $s0
  addiu $a0, $sp, 0x20
  lh $a2, 0x1c($sp)
  lw $s0, 0x1c($sp)
  jal 0x8001e8e8
  move $a1, $s1
  lw $a0, 0x20($sp)
  lui $v0, 0x8000
  beq $a0, $v0, .L80022a24
  lui $v1, 0xfff8
  lw $v0, -0x4a2c($s5)
  addu $v1, $a0, $v1
  slt $v0, $v1, $v0
  bnez $v0, .L80022a24
  lui $v0, 0x800f
  sw $s0, -0x4a0c($v0)
  lui $v0, 0x800f
  sw $v1, -0x4a2c($s5)
  sw $s3, -0x4a14($v0)
.L80022a24:
  lw $v0, ($s1)
  lw $v1, 4($s1)
  lui $t0, 0x800f
  sw $v0, 8($s1)
  sw $v1, 0xc($s1)
  lw $v0, -0x4a68($t0)
  lw $a1, 0xc($s1)
  sw $v0, ($s1)
  lw $v0, 4($s6)
  lw $v1, ($s1)
  sw $v0, 4($s1)
  lw $v0, 8($s1)
  lw $a0, 4($s1)
  subu $v0, $v0, $v1
  subu $a1, $a1, $a0
  sw $v0, 8($s1)
  move $a0, $v0
  sw $a1, 0xc($s1)
  lw $v0, 8($s6)
  nop 
  bne $a0, $v0, .L80022a8c
  lui $v0, 0x800f
  lw $v0, 0xc($s6)
  nop 
  beq $a1, $v0, .L80022b44
  lui $v0, 0x800f
.L80022a8c:
  lhu $v0, -0x4a78($v0)
  ori $t0, $zero, 0xffff
  beq $v0, $t0, .L800227fc
  move $s0, $zero
  lui $t0, 0x800f
  addiu $t0, $t0, -0x4a78
  lhu $v0, 2($t0)
  ori $t0, $zero, 0xffff
  beq $v0, $t0, .L800227fc
  lui $t0, 0x800f
  lw $v1, -0x4a58($t0)
  nop 
  bne $v1, $s3, .L80022af4
  addiu $v0, $zero, -1
  lw $v0, -0x4a50($s7)
  nop 
  bne $a0, $v0, .L80022ae4
  nop 
  lw $v0, 4($fp)
  nop 
  beq $a1, $v0, .L800227fc
  nop 
.L80022ae4:
  sw $a0, -0x4a50($s7)
  lw $v0, 0xc($s1)
  j 0x800203e8
  sw $v0, 4($fp)
.L80022af4:
  bne $v1, $v0, .L80022b1c
  addiu $s0, $zero, 1
  lw $v0, 8($s1)
  nop 
  sw $v0, -0x4a50($s7)
  lw $v0, 0xc($s1)
  lui $t0, 0x800f
  sw $s3, -0x4a58($t0)
  sw $v0, 4($fp)
  addiu $s0, $zero, 1
.L80022b1c:
  lui $v0, 0x800f
  sw $s3, -0x4a48($v0)
  lui $v0, 0x800f
  lw $v1, -0x4a0c($v0)
  lui $v0, 0x800f
  sw $v1, -0x4a44($v0)
  lw $v1, -0x4a2c($s5)
  lui $v0, 0x800f
  j 0x8002042c
  sw $v1, -0x4a40($v0)
.L80022b44:
  move $a0, $s3
  jal 0x8001e340
  move $a1, $s1
  move $s0, $v0
  bnez $s0, .L8002286c
  move $a0, $s3
  bnez $s0, .L80022738
  nop 
  lui $v0, 0x800f
.L80022b68:
  lw $s4, -0x4a14($v0)
  lui $v0, 0x800f
  lw $s2, -0x4a0c($v0)
  lh $a0, -0x4a0c($v0)
  lw $v0, ($s1)
  lw $a1, 8($s1)
  lw $v1, 4($s1)
  lw $a2, 0xc($s1)
  addu $v0, $v0, $a1
  sw $v0, ($s1)
  lui $v0, 0x800f
  lw $s0, -0x4a2c($v0)
  addu $v1, $v1, $a2
  jal 0x8001e56c
  sw $v1, 4($s1)
  lui $v1, 0xffff
  and $s2, $s2, $v1
  andi $v0, $v0, 0xffff
  or $s2, $s2, $v0
  addiu $v0, $zero, -1
  beq $s0, $v0, .L80022bf4
  addiu $a0, $zero, 1
  lui $v0, 0x800f
  lbu $v0, -0x4a04($v0)
  nop 
  beqz $v0, .L80022bf4
  move $a0, $zero
  lui $v0, 0x8000
  beq $s0, $v0, .L80022bf4
  nop 
  addiu $a0, $zero, 1
  lw $v0, 4($s1)
  addu $v1, $s0, $a0
  addu $v0, $v0, $v1
  sw $v0, 4($s1)
.L80022bf4:
  beqz $a0, .L80022c28
  lui $v1, 0x800f
  lhu $v0, -0x4a30($v1)
  nop 
  ori $v0, $v0, 1
  sh $v0, -0x4a30($v1)
  sra $v1, $s2, 0x10
  addiu $v0, $zero, 9
  bne $v1, $v0, .L80022c20
  nop 
  move $a0, $zero
.L80022c20:
  bnez $a0, .L80022c30
  nop 
.L80022c28:
  lui $v0, 0x800f
  addiu $s4, $v0, -0x4730
.L80022c30:
  lw $v0, ($s1)
  lw $v1, 4($s1)
  sw $v0, 8($s1)
  beqz $s3, .L80022c68
  sw $v1, 0xc($s1)
  lw $v1, 0x14($s3)
  nop 
  addu $v0, $v0, $v1
  sw $v0, 8($s1)
  lw $v0, 0xc($s1)
  lw $v1, 0x18($s3)
  nop 
  addu $v0, $v0, $v1
  sw $v0, 0xc($s1)
.L80022c68:
  lui $v0, 0x800f
  lw $v1, -0x4a70($v0)
  addiu $v0, $v0, -0x4a70
  sw $v1, ($s1)
  lw $v0, 4($v0)
  move $s3, $s4
  beqz $s3, .L80022cd8
  sw $v0, 4($s1)
  move $v0, $v1
  lw $v1, 0x1c($s3)
  nop 
  subu $v0, $v0, $v1
  sw $v0, ($s1)
  lw $v0, 4($s1)
  lw $v1, 0x20($s3)
  nop 
  subu $v0, $v0, $v1
  sw $v0, 4($s1)
  lw $v0, 8($s1)
  lw $v1, 0x14($s3)
  nop 
  subu $v0, $v0, $v1
  sw $v0, 8($s1)
  lw $v0, 0xc($s1)
  lw $v1, 0x18($s3)
  nop 
  subu $v0, $v0, $v1
  sw $v0, 0xc($s1)
.L80022cd8:
  lw $v0, 8($s1)
  lw $a0, ($s1)
  lw $v1, 0xc($s1)
  lw $a1, 4($s1)
  subu $v0, $v0, $a0
  subu $v1, $v1, $a1
  sw $v0, 8($s1)
  move $v0, $a0
  sw $v1, 0xc($s1)
  move $v1, $a1
  lw $a0, 8($s1)
  lw $a1, 0xc($s1)
  addu $v0, $v0, $a0
  addu $v1, $v1, $a1
  sw $v0, ($s1)
  sw $v1, 4($s1)
  lw $t0, 0x5c($sp)
  nop 
  beqz $t0, .L80022d34
  lui $v0, 0x800f
  lhu $v0, -0x4a30($v0)
  nop 
  sh $v0, ($t0)
.L80022d34:
  lw $t0, 0x58($sp)
  nop 
  beqz $t0, .L80022d50
  lui $v0, 0x800f
  lhu $v0, -0x4a32($v0)
  nop 
  sh $v0, ($t0)
.L80022d50:
  lw $t0, 0x60($sp)
  nop 
  beqz $t0, .L80022d64
  sra $v0, $s2, 0x10
  sh $v0, ($t0)
.L80022d64:
  lw $t0, 0x64($sp)
  nop 
  beqz $t0, .L80022d78
  move $v0, $s3
  sh $s2, ($t0)
.L80022d78:
  lw $ra, 0x4c($sp)
  lw $fp, 0x48($sp)
  lw $s7, 0x44($sp)
  lw $s6, 0x40($sp)
  lw $s5, 0x3c($sp)
  lw $s4, 0x38($sp)
  lw $s3, 0x34($sp)
  lw $s2, 0x30($sp)
  lw $s1, 0x2c($sp)
  lw $s0, 0x28($sp)
  jr $ra
  addiu $sp, $sp, 0x50
