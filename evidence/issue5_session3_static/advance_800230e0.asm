.set noat
.set noreorder
.text

.global FUN_800230e0
FUN_800230e0:
  addiu $sp, $sp, -0x50
  sw $s7, 0x44($sp)
  move $s7, $a0
  sw $s1, 0x2c($sp)
  move $s1, $a1
  sw $fp, 0x48($sp)
  move $fp, $a2
  sw $ra, 0x4c($sp)
  sw $s6, 0x40($sp)
  sw $s5, 0x3c($sp)
  sw $s4, 0x38($sp)
  sw $s3, 0x34($sp)
  sw $s2, 0x30($sp)
  sw $s0, 0x28($sp)
  sw $a3, 0x5c($sp)
  lw $s2, ($s7)
  lw $v1, ($s1)
  lui $v0, 0x800f
  sw $zero, -0x4a0c($v0)
  lui $v0, 0x800f
  sh $zero, -0x4a30($v0)
  lui $v0, 0x800f
  sw $v1, -0x4a68($v0)
  lw $v1, 4($s1)
  addiu $v0, $v0, -0x4a68
  sw $s2, 8($v0)
  sw $v1, 4($v0)
  lw $v0, 0xc($s1)
  lui $s0, 0x800f
  beqz $s2, .L80023184
  sw $v0, -0x4a2c($s0)
  lw $v0, ($s1)
  lw $v1, 0x14($s2)
  nop 
  addu $v0, $v0, $v1
  sw $v0, ($s1)
  lw $v0, 4($s1)
  lw $v1, 0x18($s2)
  nop 
  addu $v0, $v0, $v1
  sw $v0, 4($s1)
.L80023184:
  move $a0, $zero
  move $a1, $s1
  lw $v0, ($s1)
  lui $v1, 0x800f
  sw $v0, -0x4a70($v1)
  lw $v0, 4($s1)
  addiu $v1, $v1, -0x4a70
  sw $v0, 4($v1)
  jal 0x8001e100
  sw $zero, 8($s1)
  move $a0, $zero
  jal 0x8001e340
  move $a1, $s1
  beqz $v0, .L800233a0
  move $s2, $v0
  lui $s6, 0x800f
  lui $s5, 0x800f
  move $s4, $s0
.L800231cc:
  move $s3, $zero
  addiu $a0, $sp, 0x10
  lw $v0, ($s1)
  lw $v1, 0x14($s2)
  move $a1, $s2
  sh $zero, -0x4a3a($s6)
  sh $zero, -0x4a38($s5)
  subu $v0, $v0, $v1
  sw $v0, ($s1)
  lw $v0, 4($s1)
  lw $v1, 0x18($s2)
  lh $a2, 2($s1)
  subu $v0, $v0, $v1
  sw $v0, 4($s1)
  lh $a3, 6($s1)
  lui $v0, 0xfff8
  jal 0x8001e1d4
  sw $v0, 0xc($s1)
  addiu $a0, $sp, 0x14
  lw $s0, 0x10($sp)
  lw $a1, 8($s1)
  lw $a2, 0xc($s1)
  move $a3, $s0
  sra $v0, $a3, 0x10
  sh $v0, -0x4a3a($s6)
  jal 0x8001eba0
  sh $a3, -0x4a38($s5)
  addiu $a0, $sp, 0x18
  lh $a2, 0x14($sp)
  lw $s0, 0x14($sp)
  jal 0x8001e8e8
  move $a1, $s1
  lw $a0, 0x18($sp)
  lui $v0, 0x8000
  sltu $v0, $v0, $a0
  bnez $v0, .L800232dc
  lui $v0, 0x8000
  lw $v1, 0xc($s1)
  lw $v0, 4($s1)
  move $s3, $v1
  addu $v0, $v0, $v1
  sw $v0, 4($s1)
.L80023274:
  addiu $a0, $sp, 0x1c
  lh $a2, 2($s1)
  lh $a3, 6($s1)
  jal 0x8001e1d4
  move $a1, $s2
  lw $a1, 8($s1)
  lw $a2, 0xc($s1)
  lw $a3, 0x1c($sp)
  jal 0x8001eba0
  addiu $a0, $sp, 0x20
  addiu $v0, $zero, 0xf
  lhu $v1, -0x4a38($s5)
  lw $s0, 0x20($sp)
  bne $v1, $v0, .L800232b8
  andi $v0, $s0, 0xffff
  beq $s0, $v1, .L80023348
  nop 
.L800232b8:
  beqz $v0, .L80023348
  sh $s0, -0x4a38($s5)
  addiu $a0, $sp, 0x24
  move $a1, $s1
  sll $a2, $s0, 0x10
  jal 0x8001e8e8
  sra $a2, $a2, 0x10
  lw $a0, 0x24($sp)
  lui $v0, 0x8000
.L800232dc:
  beq $a0, $v0, .L80023348
  nop 
  lw $v0, 4($s1)
  lw $v1, -0x4a2c($s4)
  addu $v0, $v0, $a0
  addu $a0, $a0, $s3
  slt $v1, $v1, $a0
  beqz $v1, .L8002336c
  sw $v0, 4($s1)
  move $v1, $v0
  lui $v0, 0x800f
  sw $s0, -0x4a0c($v0)
  lw $v0, ($s1)
  addiu $v1, $v1, 1
  sw $v1, 4($s1)
  lui $v1, 0x800f
  sw $a0, -0x4a2c($s4)
  lui $a0, 0x800f
  sw $v0, -0x4a68($v1)
  lw $a1, 4($s1)
  lhu $v0, -0x4a30($a0)
  addiu $v1, $v1, -0x4a68
  sw $s2, 8($v1)
  ori $v0, $v0, 1
  sh $v0, -0x4a30($a0)
  j 0x80020b0c
  sw $a1, 4($v1)
.L80023348:
  lw $v0, 0xc($s1)
  lw $a0, 0xc($s1)
  lw $v1, -0x4a2c($s4)
  addu $s3, $s3, $v0
  lw $v0, 4($s1)
  slt $v1, $s3, $v1
  addu $v0, $v0, $a0
  beqz $v1, .L80023274
  sw $v0, 4($s1)
.L8002336c:
  lui $v0, 0x800f
  move $a0, $zero
  lw $v1, -0x4a70($v0)
  addiu $v0, $v0, -0x4a70
  sw $v1, ($s1)
  lw $v1, 4($v0)
  lw $v0, -0x4a2c($s4)
  move $a1, $s1
  sw $v0, 0xc($s1)
  jal 0x8001e340
  sw $v1, 4($s1)
  bnez $v0, .L800231cc
  move $s2, $v0
.L800233a0:
  lui $v0, 0x800f
  lui $v1, 0x800f
  lw $s0, -0x4a0c($v0)
  lw $v0, -0x4a68($v1)
  addiu $v1, $v1, -0x4a68
  sll $a0, $s0, 0x10
  sw $v0, ($s1)
  lw $v0, 4($v1)
  nop 
  sw $v0, 4($s1)
  lw $s2, 8($v1)
  jal 0x8001e56c
  sra $a0, $a0, 0x10
  move $s3, $s0
  lui $v1, 0xffff
  and $s0, $s0, $v1
  andi $v0, $v0, 0xffff
  or $s0, $s0, $v0
  sra $v1, $s0, 0x10
  addiu $v0, $zero, 9
  bne $v1, $v0, .L8002345c
  lui $v1, 0x800f
  beqz $s2, .L8002342c
  lui $v0, 0x800f
  lw $v0, ($s1)
  lw $v1, 0x14($s2)
  nop 
  addu $v0, $v0, $v1
  sw $v0, ($s1)
  lw $v0, 4($s1)
  lw $v1, 0x18($s2)
  nop 
  addu $v0, $v0, $v1
  sw $v0, 4($s1)
  lui $v0, 0x800f
.L8002342c:
  addiu $s2, $v0, -0x4730
  lw $v0, ($s1)
  lw $v1, 0x14($s2)
  nop 
  subu $v0, $v0, $v1
  sw $v0, ($s1)
  lw $v0, 4($s1)
  lw $v1, 0x18($s2)
  nop 
  subu $v0, $v0, $v1
  sw $v0, 4($s1)
  lui $v1, 0x800f
.L8002345c:
  lui $v0, 0x800f
  sw $s2, ($s7)
  sh $s3, ($fp)
  lhu $v0, -0x4a30($v0)
  lw $v1, -0x4a2c($v1)
  lw $t0, 0x5c($sp)
  addiu $v1, $v1, 1
  sw $v1, ($t0)
  lw $v1, 0x60($sp)
  nop 
  sw $s0, ($v1)
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
  andi $v0, $v0, 1
  jr $ra
  addiu $sp, $sp, 0x50
