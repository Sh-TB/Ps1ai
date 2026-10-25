.set noat
.set noreorder
.text

.global FUN_80021128
FUN_80021128:
  addiu $sp, $sp, -0x28
  move $t0, $a0
  lui $v0, 0x8001
  addiu $t4, $v0, 0xdb8
  lwl $t1, 3($t4)
  lwr $t1, ($t4)
  lwl $t2, 7($t4)
  lwr $t2, 4($t4)
  lwl $t3, 0xb($t4)
  lwr $t3, 8($t4)
  swl $t1, 3($sp)
  swr $t1, ($sp)
  swl $t2, 7($sp)
  swr $t2, 4($sp)
  swl $t3, 0xb($sp)
  swr $t3, 8($sp)
  lwl $t1, 0xf($t4)
  lwr $t1, 0xc($t4)
  lwl $t2, 0x13($t4)
  lwr $t2, 0x10($t4)
  lwl $t3, 0x17($t4)
  lwr $t3, 0x14($t4)
  swl $t1, 0xf($sp)
  swr $t1, 0xc($sp)
  swl $t2, 0x13($sp)
  swr $t2, 0x10($sp)
  swl $t3, 0x17($sp)
  swr $t3, 0x14($sp)
  lwl $t1, 0x1b($t4)
  lwr $t1, 0x18($t4)
  lb $t2, 0x1c($t4)
  lb $t3, 0x1d($t4)
  swl $t1, 0x1b($sp)
  swr $t1, 0x18($sp)
  sb $t2, 0x1c($sp)
  sb $t3, 0x1d($sp)
  lw $v0, 8($t0)
  nop 
  bnez $v0, .L800211d8
  lui $v0, 0x800f
  lw $v0, 0xc($t0)
  nop 
  beqz $v0, .L800219c0
  lui $v0, 0x800f
.L800211d8:
  lw $a3, -0x4a78($v0)
  lh $v0, -0x4a78($v0)
  addiu $v1, $zero, -1
  beq $v0, $v1, .L800211f4
  sra $v0, $a3, 0x10
  bne $v0, $v1, .L80021200
  lui $v0, 0x800f
.L800211f4:
  sw $zero, 8($t0)
  j 0x8001f620
  sw $zero, 0xc($t0)
.L80021200:
  lhu $v1, -0x4a3a($v0)
  addiu $v0, $zero, 9
  bne $v1, $v0, .L80021214
  sll $v0, $a1, 0x10
  ori $a3, $a3, 0xffff
.L80021214:
  sra $v0, $v0, 0x10
  addu $v0, $sp, $v0
  lbu $a0, ($v0)
  nop 
  addiu $v1, $a0, -1
  sltiu $v0, $v1, 0xd
  beqz $v0, .L800219c0
  lui $v0, 0x8001
  addiu $v0, $v0, 0xe14
  sll $v1, $v1, 2
  addu $v1, $v1, $v0
  lw $v0, ($v1)
  nop 
  jr $v0
  nop 
  addiu $v0, $zero, 8
  bne $a0, $v0, .L80021298
  lui $a1, 0x800f
  lui $v1, 0x800f
  addiu $v0, $zero, -0x3600
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lui $v1, 0x800f
  lhu $v0, -0x4a30($a0)
  lbu $v1, -0x4a76($v1)
  ori $v0, $v0, 0x12
  beqz $v1, .L800212b0
  sh $v0, -0x4a30($a0)
  lw $v0, 0xc($t0)
  nop 
  addiu $v0, $v0, -1
  j 0x8001ef10
  sw $v0, 0xc($t0)
.L80021298:
  lui $a0, 0x800f
  lhu $v0, -0x4a30($a1)
  addiu $v1, $zero, 0x4a00
  sh $v1, -0x4a32($a0)
  ori $v0, $v0, 0x42
  sh $v0, -0x4a30($a1)
.L800212b0:
  beqz $a3, .L800213bc
  nop 
  lw $a2, 0xc($t0)
  lw $v0, 8($t0)
  sll $a2, $a2, 2
  subu $a2, $a2, $v0
  beqz $a2, .L800219c0
  nop 
  bltz $a2, .L800212e4
  lui $v0, 0xffff
  and $a2, $a2, $v0
  j 0x8001ef4c
  ori $a2, $a2, 0xff00
.L800212e4:
  and $a2, $a2, $v0
  ori $a2, $a2, 0xff
  and $v0, $a3, $a2
  lui $v1, 0xffff
  and $a3, $a3, $v1
  andi $v0, $v0, 0xffff
  or $a3, $a3, $v0
  sll $v0, $a3, 0x10
  beqz $v0, .L80021368
  lui $v0, 0x800f
  addiu $v0, $v0, -0x4a78
  lhu $v1, 2($v0)
  nop 
  or $v1, $v1, $a3
  sh $v1, 2($v0)
  sll $v0, $a3, 0x18
  beqz $v0, .L8002133c
  nop 
  lw $v0, 8($t0)
  nop 
  addiu $v0, $v0, 3
  sw $v0, 8($t0)
.L8002133c:
  lw $v1, 8($t0)
  nop 
  bgez $v1, .L80021350
  nop 
  addiu $v1, $v1, 3
.L80021350:
  sra $v1, $v1, 2
  sw $v1, 8($t0)
  move $v0, $v1
  sll $v0, $v0, 2
  sw $v1, 0xc($t0)
  sw $v0, 8($t0)
.L80021368:
  sra $v1, $a3, 0x10
  andi $a3, $a3, 0xffff
  nor $v0, $zero, $a2
  and $v0, $v0, $v1
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  sra $a0, $a3, 0x10
  beqz $a0, .L800213b4
  lui $v1, 0x800f
  lhu $v0, -0x4a78($v1)
  nop 
  or $v0, $v0, $a0
  sh $v0, -0x4a78($v1)
  lw $v1, 0xc($t0)
  ldc1 $f22, 0x148($sp)
  .byte 0xc5, 0xe8, 0x5c, 0x64
  pref 0x10, -0x4718($gp)
  sdc1 $f13, -0x4c92($v1)
  .byte 0x81, 0x2a, 0x77, 0xf0
.L800213b4:
  swl $s4, -0x24c2($t4)
  .byte 0x3b, 0xa7, 0xaa, 0x65
.L800213bc:
  lw $s6, -0x7dc5($s2)
  lwc1 $f26, 0x4e01($t8)
  swl $s2, -0x57f6($s7)
  .byte 0xda, 0xa0, 0xa9, 0x72
  addi $t7, $sp, -0x25a4
  lhu $t3, 0x12ba($k0)
  pref 9, 0x3e1e($t5)
  jal 0x8546e448
  .byte 0x80, 0x97, 0x89, 0x63
  .byte 0xd3, 0xab, 0x6d, 0x60
  addiu $ra, $t0, 0x728d
  ldc1 $f13, -0x6e5($t6)
  beq $t5, $a3, 0x80002884
  swc1 $f15, -0x64a7($s2)
  .byte 0x4c, 0x74, 0xa1, 0x49
  sh $t7, -0x1ca9($s1)
  ori $fp, $t2, 0x447e
  ldc2 $5, -0x4c38($t9)
  lbu $t4, -0x5ec3($ra)
  swl $gp, 0xd71($sp)
  jalx 0x81e853c8
  andi $a0, $t4, 0x1d56
  .byte 0xa7, 0xde, 0x7c, 0x3e
  swc1 $f31, -0x68f1($v1)
  .byte 0x9f, 0xa4, 0x49, 0x5b
  .byte 0x90, 0xf9, 0x45, 0xee
  .byte 0x07, 0xf6, 0x82, 0xf1
  .byte 0x1a, 0x53, 0xc5, 0x61
  .byte 0xcb, 0xf1, 0x6a, 0x44
  jal 0x85fae414
  lwc1 $f5, 0x6286($t6)
  bltzl $t6, 0x800139f8
  .byte 0x27, 0x1f, 0x26, 0xdc
  swr $k1, -0x197c($s6)
  sdc2 $27, 0x11a($zero)
  lh $ra, 0x7d0c($k1)
  swc2 $9, 0x6215($v1)
  addi $v1, $t9, -0x1f5e
  .byte 0x5f, 0x0f, 0x4f, 0x72
  .byte 0x0b, 0xa3, 0xa4, 0x1f
  lwc2 $21, -0x4a76($v0)
  jalx 0x86bcd790
  .byte 0x19, 0x0a, 0x1e, 0x5a
  .byte 0xb6, 0x89, 0x12, 0xd2
  lwc1 $f4, -0x74c5($t2)
  .byte 0x40, 0xfb, 0xb9, 0xd3
  addi $t4, $a1, -0x65fb
  slti $v1, $sp, 0x3a9c
  ldc1 $f20, 0x519($a1)
  .byte 0xaf, 0xfa, 0x1b, 0xd2
  bz.b $w1, 0x8003b84c
  sb $a3, -0x40e9($s7)
  sw $v1, 0x3447($t2)
  pref 0x14, 0xda6($k0)
  .byte 0xf9, 0x65, 0x25, 0x5d
  sw $t1, -0x2a05($v1)
  beql $sp, $t2, 0x8000efd4
  sc $a1, 0x564($t6)
  .byte 0x8a, 0xe5, 0x8f, 0x5f
  .byte 0x19, 0x94, 0x96, 0x1c
  addiu $at, $s2, -0x53eb
  lb $t7, -0x156c($s7)
  ldc2 $25, 0x20c2($t0)
  .byte 0x00, 0xff, 0xff, 0xff
  .byte 0xff, 0xff, 0xff, 0xff
  .byte 0xff, 0xff, 0xff, 0x00
  .byte 0x00, 0x35, 0x10, 0x02
  sll $zero, $t0, 0
  sll $zero, $t0, 0
  nop 
  move $v0, $v1
  sll $v0, $v0, 2
  sw $v1, 8($t0)
  sw $v0, 0xc($t0)
  bnez $a3, .L80021af0
  nop 
  lw $a2, 0xc($t0)
  lw $v0, 8($t0)
  sll $a2, $a2, 2
  beq $a2, $v0, .L80021af0
  sll $v0, $v0, 2
  lw $v1, 0xc($t0)
  sw $v0, 8($t0)
  addu $v1, $v0, $v1
  andi $v0, $v1, 8
  beqz $v0, .L80021524
  sw $v1, 8($t0)
  sra $v0, $v1, 4
  j 0x8001f058
  addiu $v0, $v0, 1
.L80021524:
  sra $v0, $v1, 4
  sw $v0, 8($t0)
  lw $v1, 8($t0)
  nop 
  move $v0, $v1
  sll $v0, $v0, 2
  sw $v1, 0xc($t0)
  j 0x8001f620
  sw $v0, 8($t0)
  addiu $v0, $zero, 9
  bne $a0, $v0, .L80021590
  lui $a1, 0x800f
  lui $v1, 0x800f
  addiu $v0, $zero, -0x2000
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lui $v1, 0x800f
  lhu $v0, -0x4a30($a0)
  lbu $v1, -0x4a76($v1)
  ori $v0, $v0, 0x12
  bnez $v1, .L800215a8
  sh $v0, -0x4a30($a0)
  lw $v0, 0xc($t0)
  nop 
  addiu $v0, $v0, -1
  j 0x8001f0d8
  sw $v0, 0xc($t0)
.L80021590:
  lui $a0, 0x800f
  lhu $v0, -0x4a30($a1)
  addiu $v1, $zero, 0x6000
  sh $v1, -0x4a32($a0)
  ori $v0, $v0, 0x42
  sh $v0, -0x4a30($a1)
.L800215a8:
  beqz $a3, .L80021668
  nop 
  lw $v0, 0xc($t0)
  lw $v1, 8($t0)
  nop 
  beq $v0, $v1, .L80021af0
  slt $v0, $v0, $v1
  bnez $v0, .L800215d8
  lui $v0, 0xffff
  and $a2, $a2, $v0
  j 0x8001f110
  ori $a2, $a2, 0xff00
.L800215d8:
  and $a2, $a2, $v0
  ori $a2, $a2, 0xff
  and $v0, $a3, $a2
  lui $a0, 0xffff
  and $a3, $a3, $a0
  andi $v0, $v0, 0xffff
  or $a3, $a3, $v0
  sll $v0, $a3, 0x10
  beqz $v0, .L80021620
  lui $v0, 0x800f
  addiu $v0, $v0, -0x4a78
  lhu $v1, 2($v0)
  nop 
  or $v1, $v1, $a3
  sh $v1, 2($v0)
  lw $v0, 8($t0)
  nop 
  sw $v0, 0xc($t0)
.L80021620:
  sra $v1, $a3, 0x10
  andi $a3, $a3, 0xffff
  nor $v0, $zero, $a2
  and $v0, $v0, $v1
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  sra $a0, $a3, 0x10
  beqz $a0, .L80021660
  lui $v0, 0x800f
  lhu $v1, -0x4a78($v0)
  nop 
  or $v1, $v1, $a0
  sh $v1, -0x4a78($v0)
  lw $v0, 0xc($t0)
  nop 
  sw $v0, 8($t0)
.L80021660:
  bnez $a3, .L80021af0
  nop 
.L80021668:
  lw $v1, 0xc($t0)
  lw $v0, 8($t0)
  nop 
  beq $v1, $v0, .L80021af0
  addu $v1, $v0, $v1
  andi $v0, $v1, 1
  beqz $v0, .L80021694
  sw $v1, 8($t0)
  sra $v0, $v1, 1
  j 0x8001f1c8
  addiu $v0, $v0, 1
.L80021694:
  sra $v0, $v1, 1
  sw $v0, 8($t0)
  lw $v0, 8($t0)
  j 0x8001f620
  sw $v0, 0xc($t0)
  addiu $v0, $zero, 0xa
  bne $a0, $v0, .L800216f0
  lui $a1, 0x800f
  lui $v1, 0x800f
  addiu $v0, $zero, -0x4a00
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lui $v1, 0x800f
  lhu $v0, -0x4a30($a0)
  lbu $v1, -0x4a76($v1)
  ori $v0, $v0, 0x12
  bnez $v1, .L80021708
  sh $v0, -0x4a30($a0)
  lw $v0, 0xc($t0)
  nop 
  addiu $v0, $v0, -1
  j 0x8001f238
  sw $v0, 0xc($t0)
.L800216f0:
  lui $a0, 0x800f
  lhu $v0, -0x4a30($a1)
  addiu $v1, $zero, 0x3600
  sh $v1, -0x4a32($a0)
  ori $v0, $v0, 0x42
  sh $v0, -0x4a30($a1)
.L80021708:
  beqz $a3, .L8002181c
  nop 
  lw $a2, 0xc($t0)
  lw $v0, 8($t0)
  sll $a2, $a2, 2
  addu $a2, $a2, $v0
  beqz $a2, .L80021af0
  nop 
  bgez $a2, .L8002173c
  lui $v0, 0xffff
  and $a2, $a2, $v0
  j 0x8001f274
  ori $a2, $a2, 0xff00
.L8002173c:
  and $a2, $a2, $v0
  ori $a2, $a2, 0xff
  and $v0, $a3, $a2
  lui $v1, 0xffff
  and $a3, $a3, $v1
  andi $v0, $v0, 0xffff
  or $a3, $a3, $v0
  sll $v0, $a3, 0x10
  beqz $v0, .L800217c0
  sll $v0, $a3, 0x18
  beqz $v0, .L8002177c
  nor $a0, $zero, $a3
  lw $v0, 8($t0)
  nop 
  addiu $v0, $v0, 3
  sw $v0, 8($t0)
.L8002177c:
  and $a3, $a3, $v1
  andi $a0, $a0, 0xffff
  lui $v1, 0x800f
  addiu $v1, $v1, -0x4a78
  lhu $v0, 2($v1)
  or $a3, $a3, $a0
  or $v0, $v0, $a3
  sh $v0, 2($v1)
  lw $v0, 8($t0)
  nop 
  sra $v0, $v0, 2
  sw $v0, 8($t0)
  move $v1, $v0
  negu $v0, $v0
  sll $v1, $v1, 2
  sw $v0, 0xc($t0)
  sw $v1, 8($t0)
.L800217c0:
  sra $v0, $a3, 0x10
  andi $a3, $a3, 0xffff
  and $v0, $v0, $a2
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  sra $v0, $a3, 0x10
  beqz $v0, .L80021814
  nor $v0, $zero, $v0
  andi $a3, $a3, 0xffff
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  lui $a0, 0x800f
  lhu $v0, -0x4a78($a0)
  sra $v1, $a3, 0x10
  or $v0, $v0, $v1
  sh $v0, -0x4a78($a0)
  lw $v0, 0xc($t0)
  nop 
  sll $v0, $v0, 2
  negu $v0, $v0
  sw $v0, 8($t0)
.L80021814:
  bnez $a3, .L80021af0
  nop 
.L8002181c:
  lw $a2, 0xc($t0)
  lw $v0, 8($t0)
  sll $a2, $a2, 2
  beq $a2, $v0, .L80021af0
  sll $v0, $v0, 2
  lw $v1, 0xc($t0)
  sw $v0, 8($t0)
  subu $v1, $v1, $v0
  andi $v0, $v1, 0x10
  beqz $v0, .L80021854
  sw $v1, 0xc($t0)
  sra $v0, $v1, 4
  j 0x8001f388
  addiu $v0, $v0, 1
.L80021854:
  sra $v0, $v1, 4
  sw $v0, 0xc($t0)
  lw $v0, 0xc($t0)
  nop 
  negu $v0, $v0
  sll $v0, $v0, 2
  j 0x8001f620
  sw $v0, 8($t0)
  addiu $v0, $zero, 0xb
  bne $a0, $v0, .L800218bc
  lui $a1, 0x800f
  lui $v1, 0x800f
  addiu $v0, $zero, -0x6000
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lui $v1, 0x800f
  lhu $v0, -0x4a30($a0)
  lbu $v1, -0x4a76($v1)
  ori $v0, $v0, 0x12
  beqz $v1, .L800218d4
  sh $v0, -0x4a30($a0)
  lw $v0, 0xc($t0)
  nop 
  addiu $v0, $v0, -1
  j 0x8001f404
  sw $v0, 0xc($t0)
.L800218bc:
  lui $a0, 0x800f
  lhu $v0, -0x4a30($a1)
  addiu $v1, $zero, 0x2000
  sh $v1, -0x4a32($a0)
  ori $v0, $v0, 0x42
  sh $v0, -0x4a30($a1)
.L800218d4:
  beqz $a3, .L800219b8
  nop 
  lw $a2, 8($t0)
  lw $v0, 0xc($t0)
  nop 
  addu $a2, $a2, $v0
  beqz $a2, .L80021af0
  nop 
  bgez $a2, .L80021908
  lui $v0, 0xffff
  and $a2, $a2, $v0
  j 0x8001f440
  ori $a2, $a2, 0xff00
.L80021908:
  and $a2, $a2, $v0
  ori $a2, $a2, 0xff
  and $v0, $a3, $a2
  lui $v1, 0xffff
  and $a3, $a3, $v1
  andi $v0, $v0, 0xffff
  or $a3, $a3, $v0
  sll $v0, $a3, 0x10
  beqz $v0, .L80021960
  nor $a0, $zero, $a3
  and $a3, $a3, $v1
  andi $a0, $a0, 0xffff
  lui $v1, 0x800f
  addiu $v1, $v1, -0x4a78
  lhu $v0, 2($v1)
  or $a3, $a3, $a0
  or $v0, $v0, $a3
  sh $v0, 2($v1)
  lw $v0, 8($t0)
  nop 
  negu $v0, $v0
  sw $v0, 0xc($t0)
.L80021960:
  sra $v0, $a3, 0x10
  andi $a3, $a3, 0xffff
  and $v0, $v0, $a2
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  sra $v0, $a3, 0x10
  beqz $v0, .L800219b0
  nor $v0, $zero, $v0
  andi $a3, $a3, 0xffff
  sll $v0, $v0, 0x10
  or $a3, $a3, $v0
  lui $a0, 0x800f
  lhu $v0, -0x4a78($a0)
  sra $v1, $a3, 0x10
  or $v0, $v0, $v1
  sh $v0, -0x4a78($a0)
  lw $v0, 0xc($t0)
  nop 
  negu $v0, $v0
  sw $v0, 8($t0)
.L800219b0:
  bnez $a3, .L80021af0
  nop 
.L800219b8:
  lw $a2, 8($t0)
  lw $v0, 0xc($t0)
.L800219c0:
  move $v1, $a2
  addu $a2, $a2, $v0
  beqz $a2, .L80021af0
  subu $v1, $v0, $v1
  andi $v0, $v1, 1
  beqz $v0, .L800219f0
  sw $v1, 0xc($t0)
  srl $v0, $v1, 0x1f
  addu $v0, $v1, $v0
  sra $v0, $v0, 1
  j 0x8001f52c
  addiu $v0, $v0, 1
.L800219f0:
  srl $v0, $v1, 0x1f
  addu $v0, $v1, $v0
  sra $v0, $v0, 1
  sw $v0, 0xc($t0)
  lw $v0, 0xc($t0)
  nop 
  negu $v0, $v0
  j 0x8001f620
  sw $v0, 8($t0)
  lui $v1, 0x800f
  addiu $v0, $zero, 0x4000
  lui $a1, 0x800f
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lhu $v1, -0x4a30($a1)
  addiu $v0, $zero, 0xff
  sb $v0, -0x4a76($a0)
  sw $zero, 0xc($t0)
  j 0x8001f61c
  ori $v1, $v1, 0x42
  lui $v1, 0x800f
  addiu $v0, $zero, -0x4000
  lui $a1, 0x800f
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lhu $v1, -0x4a30($a1)
  addiu $v0, $zero, 0xff
  sb $v0, -0x4a75($a0)
  sw $zero, 0xc($t0)
  j 0x8001f61c
  ori $v1, $v1, 0x12
  addiu $v0, $zero, 7
  bne $a0, $v0, .L80021a94
  andi $v1, $a0, 0xff
  lw $v0, 8($t0)
  nop 
  bgtz $v0, .L80021a90
  addiu $a0, $zero, 0xd
  bgez $v0, .L80021af0
  addiu $a0, $zero, 0xc
.L80021a90:
  andi $v1, $a0, 0xff
.L80021a94:
  addiu $v0, $zero, 0xd
  bne $v1, $v0, .L80021ac4
  addiu $v0, $zero, 0xc
  lui $v1, 0x800f
  addiu $v0, $zero, -0x8000
  lui $a1, 0x800f
  lui $a0, 0x800f
  sh $v0, -0x4a32($v1)
  lhu $v1, -0x4a30($a1)
  addiu $v0, $zero, 0xff
  j 0x8001f614
  sb $v0, -0x4a77($a0)
.L80021ac4:
  bne $v1, $v0, .L80021af0
  lui $v0, 0x800f
  lui $a1, 0x800f
  lhu $v1, -0x4a30($a1)
  lui $a0, 0x800f
  sh $zero, -0x4a32($v0)
  addiu $v0, $zero, 0xff
  sb $v0, -0x4a78($a0)
  sw $zero, 8($t0)
  ori $v1, $v1, 6
  sh $v1, -0x4a30($a1)
.L80021af0:
  jr $ra
  addiu $sp, $sp, 0x28
  addiu $sp, $sp, -0x18
  sll $a1, $a1, 0x10
  sra $a1, $a1, 0x10
  addiu $v0, $zero, 0xf
  bne $a1, $v0, .L80021b28
  sw $ra, 0x10($sp)
  lw $v0, 0xc($a0)
  nop 
  bgtz $v0, .L80021b28
  addiu $a1, $zero, 0xd
  bgez $v0, .L80021b30
  addiu $a1, $zero, 0xb
.L80021b28:
  jal 0x8001ed88
  nop 
.L80021b30:
  lw $ra, 0x10($sp)
  nop 
  jr $ra
  addiu $sp, $sp, 0x18
