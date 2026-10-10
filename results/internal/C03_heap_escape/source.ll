; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/C03_heap_escape/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/C03_heap_escape/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !10 {
  %2 = alloca ptr, align 8
  %3 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !16, metadata !DIExpression()), !dbg !17
  call void @llvm.dbg.declare(metadata ptr %3, metadata !18, metadata !DIExpression()), !dbg !21
  %4 = load ptr, ptr %2, align 8, !dbg !22
  store ptr %4, ptr %3, align 8, !dbg !21
  %5 = load ptr, ptr %3, align 8, !dbg !23
  store i32 1, ptr %5, align 4, !dbg !24
  ret ptr null, !dbg !25
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !26 {
  %2 = alloca ptr, align 8
  %3 = alloca ptr, align 8
  %4 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !27, metadata !DIExpression()), !dbg !28
  call void @llvm.dbg.declare(metadata ptr %3, metadata !29, metadata !DIExpression()), !dbg !30
  %5 = load ptr, ptr %2, align 8, !dbg !31
  store ptr %5, ptr %3, align 8, !dbg !30
  call void @llvm.dbg.declare(metadata ptr %4, metadata !32, metadata !DIExpression()), !dbg !33
  %6 = load ptr, ptr %3, align 8, !dbg !34
  %7 = load i32, ptr %6, align 4, !dbg !35
  store i32 %7, ptr %4, align 4, !dbg !33
  %8 = load i32, ptr %4, align 4, !dbg !36
  ret ptr null, !dbg !37
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !38 {
  %1 = alloca i32, align 4
  %2 = alloca ptr, align 8
  %3 = alloca i64, align 8
  %4 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !41, metadata !DIExpression()), !dbg !42
  %5 = call noalias ptr @malloc(i64 noundef 4) #5, !dbg !43
  store ptr %5, ptr %2, align 8, !dbg !42
  %6 = load ptr, ptr %2, align 8, !dbg !44
  %7 = icmp ne ptr %6, null, !dbg !44
  br i1 %7, label %9, label %8, !dbg !46

8:                                                ; preds = %0
  store i32 1, ptr %1, align 4, !dbg !47
  br label %20, !dbg !47

9:                                                ; preds = %0
  %10 = load ptr, ptr %2, align 8, !dbg !48
  store i32 0, ptr %10, align 4, !dbg !49
  call void @llvm.dbg.declare(metadata ptr %3, metadata !50, metadata !DIExpression()), !dbg !54
  call void @llvm.dbg.declare(metadata ptr %4, metadata !55, metadata !DIExpression()), !dbg !56
  %11 = load ptr, ptr %2, align 8, !dbg !57
  %12 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @writer, ptr noundef %11) #6, !dbg !58
  %13 = load ptr, ptr %2, align 8, !dbg !59
  %14 = call i32 @pthread_create(ptr noundef %4, ptr noundef null, ptr noundef @reader, ptr noundef %13) #6, !dbg !60
  %15 = load i64, ptr %3, align 8, !dbg !61
  %16 = call i32 @pthread_join(i64 noundef %15, ptr noundef null), !dbg !62
  %17 = load i64, ptr %4, align 8, !dbg !63
  %18 = call i32 @pthread_join(i64 noundef %17, ptr noundef null), !dbg !64
  %19 = load ptr, ptr %2, align 8, !dbg !65
  call void @free(ptr noundef %19) #6, !dbg !66
  store i32 0, ptr %1, align 4, !dbg !67
  br label %20, !dbg !67

20:                                               ; preds = %9, %8
  %21 = load i32, ptr %1, align 4, !dbg !68
  ret i32 %21, !dbg !68
}

; Function Attrs: nounwind allocsize(0)
declare noalias ptr @malloc(i64 noundef) #2

; Function Attrs: nounwind
declare i32 @pthread_create(ptr noundef, ptr noundef, ptr noundef, ptr noundef) #3

declare i32 @pthread_join(i64 noundef, ptr noundef) #4

; Function Attrs: nounwind
declare void @free(ptr noundef) #3

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nounwind allocsize(0) "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #5 = { nounwind allocsize(0) }
attributes #6 = { nounwind }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!2, !3, !4, !5, !6, !7, !8}
!llvm.ident = !{!9}

!0 = distinct !DICompileUnit(language: DW_LANG_C11, file: !1, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, splitDebugInlining: false, nameTableKind: None)
!1 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/C03_heap_escape/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "45d58c383afe67a74d37306c5ff29021")
!2 = !{i32 7, !"Dwarf Version", i32 5}
!3 = !{i32 2, !"Debug Info Version", i32 3}
!4 = !{i32 1, !"wchar_size", i32 4}
!5 = !{i32 8, !"PIC Level", i32 2}
!6 = !{i32 7, !"PIE Level", i32 2}
!7 = !{i32 7, !"uwtable", i32 2}
!8 = !{i32 7, !"frame-pointer", i32 2}
!9 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!10 = distinct !DISubprogram(name: "writer", scope: !11, file: !11, line: 4, type: !12, scopeLine: 4, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !15)
!11 = !DIFile(filename: "cases/C03_heap_escape/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "45d58c383afe67a74d37306c5ff29021")
!12 = !DISubroutineType(types: !13)
!13 = !{!14, !14}
!14 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!15 = !{}
!16 = !DILocalVariable(name: "arg", arg: 1, scope: !10, file: !11, line: 4, type: !14)
!17 = !DILocation(line: 4, column: 20, scope: !10)
!18 = !DILocalVariable(name: "p", scope: !10, file: !11, line: 5, type: !19)
!19 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: !20, size: 64)
!20 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!21 = !DILocation(line: 5, column: 10, scope: !10)
!22 = !DILocation(line: 5, column: 14, scope: !10)
!23 = !DILocation(line: 6, column: 6, scope: !10)
!24 = !DILocation(line: 6, column: 8, scope: !10)
!25 = !DILocation(line: 7, column: 5, scope: !10)
!26 = distinct !DISubprogram(name: "reader", scope: !11, file: !11, line: 10, type: !12, scopeLine: 10, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !15)
!27 = !DILocalVariable(name: "arg", arg: 1, scope: !26, file: !11, line: 10, type: !14)
!28 = !DILocation(line: 10, column: 20, scope: !26)
!29 = !DILocalVariable(name: "p", scope: !26, file: !11, line: 11, type: !19)
!30 = !DILocation(line: 11, column: 10, scope: !26)
!31 = !DILocation(line: 11, column: 14, scope: !26)
!32 = !DILocalVariable(name: "seen", scope: !26, file: !11, line: 12, type: !20)
!33 = !DILocation(line: 12, column: 9, scope: !26)
!34 = !DILocation(line: 12, column: 17, scope: !26)
!35 = !DILocation(line: 12, column: 16, scope: !26)
!36 = !DILocation(line: 13, column: 11, scope: !26)
!37 = !DILocation(line: 14, column: 5, scope: !26)
!38 = distinct !DISubprogram(name: "main", scope: !11, file: !11, line: 17, type: !39, scopeLine: 17, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !15)
!39 = !DISubroutineType(types: !40)
!40 = !{!20}
!41 = !DILocalVariable(name: "heap_value", scope: !38, file: !11, line: 18, type: !19)
!42 = !DILocation(line: 18, column: 10, scope: !38)
!43 = !DILocation(line: 18, column: 23, scope: !38)
!44 = !DILocation(line: 19, column: 10, scope: !45)
!45 = distinct !DILexicalBlock(scope: !38, file: !11, line: 19, column: 9)
!46 = !DILocation(line: 19, column: 9, scope: !38)
!47 = !DILocation(line: 19, column: 22, scope: !45)
!48 = !DILocation(line: 20, column: 6, scope: !38)
!49 = !DILocation(line: 20, column: 17, scope: !38)
!50 = !DILocalVariable(name: "first", scope: !38, file: !11, line: 21, type: !51)
!51 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !52, line: 27, baseType: !53)
!52 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!53 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!54 = !DILocation(line: 21, column: 15, scope: !38)
!55 = !DILocalVariable(name: "second", scope: !38, file: !11, line: 21, type: !51)
!56 = !DILocation(line: 21, column: 22, scope: !38)
!57 = !DILocation(line: 22, column: 39, scope: !38)
!58 = !DILocation(line: 22, column: 5, scope: !38)
!59 = !DILocation(line: 23, column: 40, scope: !38)
!60 = !DILocation(line: 23, column: 5, scope: !38)
!61 = !DILocation(line: 24, column: 18, scope: !38)
!62 = !DILocation(line: 24, column: 5, scope: !38)
!63 = !DILocation(line: 25, column: 18, scope: !38)
!64 = !DILocation(line: 25, column: 5, scope: !38)
!65 = !DILocation(line: 26, column: 10, scope: !38)
!66 = !DILocation(line: 26, column: 5, scope: !38)
!67 = !DILocation(line: 27, column: 5, scope: !38)
!68 = !DILocation(line: 28, column: 1, scope: !38)
