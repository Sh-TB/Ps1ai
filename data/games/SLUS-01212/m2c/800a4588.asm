.set noat
.set noreorder
.text

.global FUN_800a4588
FUN_800a4588:
  sw $ra, 0x24($sp)
  sb $zero, 0xb6($v0)
  lw $v1, -0x6568($s0)
  addiu $v0, $zero, 0xff
  sb $v0, 0x26($v1)
  lw $a3, -0x6568($s0)
  addiu $v0, $zero, 0x100
  sh $v0, 0x66($a3)
  lhu $v0, 0x7a($a3)
  lhu $v1, 0x7e($a3)
  move $a2, $a1
  sw $zero, 0xa8($a3)
  addiu $v0, $v0, -8
  addiu $v1, $v1, 0x12
  sh $v0, 0x7a($a3)
  addiu $v0, $a3, 0x84
  sh $v1, 0x7e($a3)
  sw $v0, 0x10($sp)
  addiu $v0, $a3, 0xcc
  sw $v0, 0x14($sp)
  addiu $v0, $a3, 0x80
  jal X_8004415c
  sw $v0, 0x18($sp)
  addiu $a1, $zero, 0x3a
  lw $a0, -0x6568($s0)
  addiu $a2, $zero, 0x100
  jal X_80019e5c
  addiu $a0, $a0, 0x2c
  lui $v0, 0x800b
  lw $v1, -0x6568($s0)
  addiu $v0, $v0, 0x179c
  jal X_800b179c
  sw $v0, ($v1)
  lw $ra, 0x24($sp)
  lw $s0, 0x20($sp)
  jr $ra
  addiu $sp, $sp, 0x28
  addiu $sp, $sp, -0x28
  sw $ra, 0x24($sp)
  jal X_800ae47c
  sw $s0, 0x20($sp)
  beqz $v0, .L800a4644
  lui $v0, 0x800d
  lui $v1, 0x800b
  lw $v0, -0x6568($v0)
  addiu $v1, $v1, 0x1838
  sw $v1, ($v0)
.L800a4644:
  lui $s0, 0x800d
  lw $a0, -0x6568($s0)
  jal X_8001ac74
  addiu $a0, $a0, 0x2c
  lw $a1, -0x6568($s0)
  nop 
  lh $v0, 0x1c($a1)
  lh $a2, 0x18($a1)
  lh $a3, 0x1a($a1)
  sw $v0, 0x10($sp)
  lhu $v0, 0x2a($a1)
  nop 
  sw $v0, 0x14($sp)
  lh $v0, 0x1e($a1)
  addiu $a0, $a1, 0x30
  sw $v0, 0x18($sp)
  lbu $v0, 0x28($a1)
  lbu $v1, 0x27($a1)
  addiu $a1, $a1, 0x78
  sll $v0, $v0, 8
  or $v1, $v1, $v0
  jal X_800196a4
  sw $v1, 0x1c($sp)
  jal X_800b16b4
  nop 
  lw $ra, 0x24($sp)
  lw $s0, 0x20($sp)
  jr $ra
  addiu $sp, $sp, 0x28
  addiu $sp, $sp, -0x28
  addiu $a0, $zero, 0xa
  addiu $a1, $zero, 0x18
  sw $s0, 0x20($sp)
  lui $s0, 0x800d
  lw $a3, -0x6568($s0)
  addiu $a2, $zero, 0x10
  sw $ra, 0x24($sp)
  addiu $v0, $a3, 0x84
  sw $v0, 0x10($sp)
  addiu $v0, $a3, 0xcc
  sw $v0, 0x14($sp)
  addiu $v0, $a3, 0x80
  jal X_8004415c
  sw $v0, 0x18($sp)
  addiu $a1, $zero, 0x3a
  lw $a0, -0x6568($s0)
  addiu $a2, $zero, 0x100
  jal X_80019e5c
  addiu $a0, $a0, 0x2c
  lui $v0, 0x800b
  lw $v1, -0x6568($s0)
  addiu $v0, $v0, 0x18ac
  jal X_800b18ac
  sw $v0, ($v1)
  lw $ra, 0x24($sp)
  lw $s0, 0x20($sp)
  jr $ra
  addiu $sp, $sp, 0x28
  addiu $sp, $sp, -0x28
  sw $ra, 0x24($sp)
  jal X_800ae47c
  sw $s0, 0x20($sp)
  beqz $v0, .L800a4754
  lui $v0, 0x800d
  lui $v1, 0x800b
  lw $v0, -0x6568($v0)
  addiu $v1, $v1, 0x1948
  sw $v1, ($v0)
.L800a4754:
  lui $s0, 0x800d
  lw $a0, -0x6568($s0)
  jal X_8001ac74
  addiu $a0, $a0, 0x2c
  lw $a1, -0x6568($s0)
  nop 
  lh $v0, 0x1c($a1)
  lh $a2, 0x18($a1)
  lh $a3, 0x1a($a1)
  sw $v0, 0x10($sp)
  lhu $v0, 0x2a($a1)
  nop 
  sw $v0, 0x14($sp)
  lh $v0, 0x1e($a1)
  addiu $a0, $a1, 0x30
  sw $v0, 0x18($sp)
  lbu $v0, 0x28($a1)
  lbu $v1, 0x27($a1)
  addiu $a1, $a1, 0x78
  sll $v0, $v0, 8
  or $v1, $v1, $v0
  jal X_800196a4
  sw $v1, 0x1c($sp)
  jal X_800b16b4
  nop 
  lw $ra, 0x24($sp)
  lw $s0, 0x20($sp)
  jr $ra
  addiu $sp, $sp, 0x28
  lui $a0, 0x800d
  lw $v1, -0x6568($a0)
  addiu $sp, $sp, -0x18
  sw $ra, 0x10($sp)
  lbu $v0, 0x28($v1)
  nop 
  ori $v0, $v0, 8
  sb $v0, 0x28($v1)
  lw $v1, -0x6568($a0)
  addiu $v0, $zero, 0x1e
  sh $v0, 0xd8($v1)
  lui $v0, 0x800b
  addiu $v0, $v0, 0x1994
  jal X_800b1994
  sw $v0, ($v1)
  lw $ra, 0x10($sp)