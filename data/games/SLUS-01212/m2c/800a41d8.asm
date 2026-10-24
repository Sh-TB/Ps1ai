.set noat
.set noreorder
.text

.global FUN_800a41d8
FUN_800a41d8:
  lw $v0, -0x6568($s0)
  nop 
  lbu $v0, 0x28($v0)
  nop 
  andi $v0, $v0, 0x80
  beqz $v0, .L800a4204
  nop 
  jal X_800b1a4c
  nop 
  j X_800b13a0
  nop 
.L800a4204:
  jal X_800af1b0
  nop 
  beqz $v0, .L800a4220
  lui $v0, 0x8001
  lw $v1, -0x6568($s0)
  addiu $v0, $v0, 0x51dc
  sw $v0, ($v1)
.L800a4220:
  lw $ra, 0x14($sp)
  lw $s0, 0x10($sp)
  jr $ra
  addiu $sp, $sp, 0x18
  addiu $sp, $sp, -0x18
  lui $v0, 0x800d
  lw $v1, -0x6568($v0)
  ori $v0, $zero, 0xffff
  sll $a0, $a0, 0x10
  sw $ra, 0x10($sp)
  sh $v0, 0x60($v1)
  sra $v1, $a0, 0x10
  sltiu $v0, $v1, 0xe
  beqz $v0, .L800a42c8
  lui $v0, 0x800a
  addiu $v0, $v0, -0x14f0
  sll $v1, $v1, 2
  addu $v1, $v1, $v0
  lw $v0, ($v1)
  nop 
  jr $v0
  nop 
  jal X_800ae0f4
  nop 
  j X_800b1448
  nop 
  jal X_800ae0b8
  nop 
  j X_800b1448
  nop 
  jal X_800ae130
  nop 
  j X_800b1448
  nop 
  jal X_800ae16c
  nop 
  j X_800b1448
  nop 
  lui $v0, 0x800d
  lw $v0, -0x6568($v0)
  nop 
  sw $zero, 0xa8($v0)
.L800a42c8:
  lw $ra, 0x10($sp)
  nop 
  jr $ra
  addiu $sp, $sp, 0x18
  addiu $sp, $sp, -0x18
  sw $s0, 0x10($sp)
  lui $s0, 0x800d
  lw $v0, -0x6568($s0)
  sw $ra, 0x14($sp)
  lbu $v1, 0xeb($v0)
  addiu $a0, $zero, 0x105
  sh $a0, 0x2c($v0)
  andi $v1, $v1, 0x40
  bnez $v1, .L800a4308
  addiu $a0, $zero, 0x73bd
  addiu $a0, $zero, 0x40
.L800a4308:
  jal X_80050b44
  nop 
  lw $v1, -0x6568($s0)
  nop 
  lbu $v0, 0x27($v1)
  nop 
  andi $v0, $v0, 0xfb
  sb $v0, 0x27($v1)
  lui $a0, 0x800a
  jal X_8005cad0
  addiu $a0, $a0, -0x4850
  lui $s0, 0x800d
  lw $v1, -0x6568($s0)
  jal X_800ae0b8
  sh $v0, 0xa4($v1)
  move $a0, $zero
  jal X_80043960
  move $a1, $a0
  jal X_800b13b0
  move $a0, $zero
  lui $v0, 0x800b
  lw $v1, -0x6568($s0)
  addiu $v0, $v0, 0x14fc
  jal X_800b14fc
  sw $v0, ($v1)
  lw $ra, 0x14($sp)
  lw $s0, 0x10($sp)
  jr $ra
  addiu $sp, $sp, 0x18
  addiu $sp, $sp, -0x20
  sw $s0, 0x10($sp)
  lui $s0, 0x800d
  sw $s1, 0x14($sp)
  lui $s1, 0x800d
  lw $v0, 0x40a0($s1)
  lw $v1, -0x6568($s0)
  sw $ra, 0x18($sp)
  lw $v0, 0x6c($v0)
  lw $a0, 0x6c($v1)
  lbu $v1, -2($v0)
  lbu $v0, -2($a0)
  nop 
  beq $v0, $v1, X_800a43d8
  nop 
  sb $v1, -2($a0)
  lw $v0, -0x6568($s0)