.set noat
.set noreorder
.text

.global FUN_8009de68
FUN_8009de68:
  lw $a0, -0x6568($s1)
  lh $v0, 0x8e($s0)
  lh $v1, 0x8e($a0)
  addiu $a1, $zero, 0x80
  slt $v0, $v0, $v1
  sll $v1, $v0, 7
  sb $v1, 0xeb($a0)
  lui $a0, 0x800d
  lw $v0, -0x6568($a0)
  nop 
  lbu $v1, 0xeb($v0)
  nop 
  and $v1, $v1, $a1
  srl $v1, $v1, 4
  sb $v1, 0xea($v0)
  sb $v1, 0xeb($v0)
  sltiu $v0, $v1, 9
  beqz $v0, .L8009decc
  nop 
  lw $v1, -0x6568($a0)
  nop 
  lbu $v0, 0xf4($v1)
  addiu $a0, $zero, 0x11
  j X_800ab060
  andi $v0, $v0, 0xfd
.L8009decc:
  lw $v1, -0x6568($a0)
  nop 
  lbu $v0, 0xf4($v1)
  addiu $a0, $zero, 0x12
  ori $v0, $v0, 2
  jal X_800a964c
  sb $v0, 0xf4($v1)
  lui $v0, 0x800d
  lui $v1, 0x800b
  lw $v0, -0x6568($v0)
  addiu $v1, $v1, -0x4f6c
  jal X_800ab094
  sw $v1, ($v0)
  lw $ra, 0x18($sp)
  lw $s1, 0x14($sp)
  lw $s0, 0x10($sp)
  jr $ra
  addiu $sp, $sp, 0x20
  addiu $sp, $sp, -0x18
  sw $ra, 0x10($sp)
  jal X_800a8924
  nop 
  jal X_800a9894
  nop 
  beqz $v0, .L8009df44
  lui $v0, 0x800d
  lui $v1, 0x800b
  lw $v0, -0x6568($v0)
  addiu $v1, $v1, -0x4f04
  sw $v1, ($v0)
.L8009df44:
  jal X_800a8ecc
  nop 
  beqz $v0, .L8009df64
  lui $v0, 0x800d
  lui $v1, 0x800b
  lw $v0, -0x6568($v0)
  addiu $v1, $v1, -0x5244
  sw $v1, ($v0)
.L8009df64:
  jal X_800a9b1c
  nop 
  lw $ra, 0x10($sp)
  nop 
  jr $ra
  addiu $sp, $sp, 0x18
  addiu $sp, $sp, -0x18
  sw $s0, 0x10($sp)
  lui $s0, 0x800d
  lw $v0, -0x6568($s0)
  sw $ra, 0x14($sp)
  lbu $v1, 0xf4($v0)
  sw $zero, 0x80($v0)
  andi $v1, $v1, 2
  bnez $v1, .L8009dfdc
  sw $zero, 0x84($v0)
  lui $a0, 0x800b
  addiu $a0, $a0, 0x7e94
  jal X_800a981c
  addiu $a1, $zero, 0x11
  lw $a0, -0x6568($s0)
  nop 
  lbu $v0, 0x27($a0)
  nop 
  andi $v0, $v0, 1
  bnez $v0, .L8009e034
  lui $v1, 0x800d
  lbu $v1, 0xeb($a0)
  j X_800ab1a4
  addiu $v0, $zero, 8
.L8009dfdc:
  lui $a0, 0x800b
  addiu $a0, $a0, 0x7efc
  jal X_800a981c
  addiu $a1, $zero, 0xd
  lw $v1, -0x6568($s0)
  nop 
  lbu $v0, 0xeb($v1)
  nop 
  addiu $v0, $v0, -9
  sb $v0, 0xeb($v1)
  lw $a0, -0x6568($s0)
  nop 
  lbu $v0, 0x27($a0)
  nop 
  andi $v0, $v0, 1
  beqz $v0, .L8009e030
  addiu $v0, $zero, 6
  lbu $v1, 0xeb($a0)
  nop 
  subu $v0, $v0, $v1
  sb $v0, 0xeb($a0)
.L8009e030:
  lui $v1, 0x800d
.L8009e034:
  lw $a0, -0x6568($v1)
  nop 
  lbu $v0, 0xeb($a0)
  nop 
  sll $v0, $v0, 1
  sb $v0, 0xeb($a0)
  lw $v0, -0x6568($v1)
  nop 
  sb $zero, 0xe9($v0)
  lui $v0, 0x800b