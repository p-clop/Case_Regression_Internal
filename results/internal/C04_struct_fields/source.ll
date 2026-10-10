; ModuleID = '/home/zhovy/work/Case_Regression_Internal/cases/C04_struct_fields/case.c'
source_filename = "/home/zhovy/work/Case_Regression_Internal/cases/C04_struct_fields/case.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

%struct.State = type { i32, i32 }

@state = dso_local global %struct.State zeroinitializer, align 4, !dbg !0

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @writer(ptr noundef %0) #0 !dbg !19 {
  %2 = alloca ptr, align 8
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !24, metadata !DIExpression()), !dbg !25
  %3 = load ptr, ptr %2, align 8, !dbg !26
  store i32 1, ptr @state, align 4, !dbg !27
  store i32 1, ptr getelementptr inbounds (%struct.State, ptr @state, i32 0, i32 1), align 4, !dbg !28
  ret ptr null, !dbg !29
}

; Function Attrs: nocallback nofree nosync nounwind speculatable willreturn memory(none)
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local ptr @reader(ptr noundef %0) #0 !dbg !30 {
  %2 = alloca ptr, align 8
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store ptr %0, ptr %2, align 8
  call void @llvm.dbg.declare(metadata ptr %2, metadata !31, metadata !DIExpression()), !dbg !32
  %5 = load ptr, ptr %2, align 8, !dbg !33
  call void @llvm.dbg.declare(metadata ptr %3, metadata !34, metadata !DIExpression()), !dbg !35
  %6 = load i32, ptr getelementptr inbounds (%struct.State, ptr @state, i32 0, i32 1), align 4, !dbg !36
  store i32 %6, ptr %3, align 4, !dbg !35
  call void @llvm.dbg.declare(metadata ptr %4, metadata !37, metadata !DIExpression()), !dbg !38
  %7 = load i32, ptr @state, align 4, !dbg !39
  store i32 %7, ptr %4, align 4, !dbg !38
  %8 = load i32, ptr %3, align 4, !dbg !40
  %9 = load i32, ptr %4, align 4, !dbg !41
  ret ptr null, !dbg !42
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !43 {
  %1 = alloca i32, align 4
  %2 = alloca i64, align 8
  %3 = alloca i64, align 8
  store i32 0, ptr %1, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !46, metadata !DIExpression()), !dbg !50
  call void @llvm.dbg.declare(metadata ptr %3, metadata !51, metadata !DIExpression()), !dbg !52
  %4 = call i32 @pthread_create(ptr noundef %2, ptr noundef null, ptr noundef @writer, ptr noundef null) #4, !dbg !53
  %5 = call i32 @pthread_create(ptr noundef %3, ptr noundef null, ptr noundef @reader, ptr noundef null) #4, !dbg !54
  %6 = load i64, ptr %2, align 8, !dbg !55
  %7 = call i32 @pthread_join(i64 noundef %6, ptr noundef null), !dbg !56
  %8 = load i64, ptr %3, align 8, !dbg !57
  %9 = call i32 @pthread_join(i64 noundef %8, ptr noundef null), !dbg !58
  ret i32 0, !dbg !59
}

; Function Attrs: nounwind
declare i32 @pthread_create(ptr noundef, ptr noundef, ptr noundef, ptr noundef) #2

declare i32 @pthread_join(i64 noundef, ptr noundef) #3

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nocallback nofree nosync nounwind speculatable willreturn memory(none) }
attributes #2 = { nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { nounwind }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!11, !12, !13, !14, !15, !16, !17}
!llvm.ident = !{!18}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "state", scope: !2, file: !5, line: 4, type: !6, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C11, file: !3, producer: "Ubuntu clang version 18.1.3 (1ubuntu1)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, globals: !4, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/zhovy/work/Case_Regression_Internal/cases/C04_struct_fields/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "fab353739b6e883370e916aee0eda969")
!4 = !{!0}
!5 = !DIFile(filename: "cases/C04_struct_fields/case.c", directory: "/home/zhovy/work/Case_Regression_Internal", checksumkind: CSK_MD5, checksum: "fab353739b6e883370e916aee0eda969")
!6 = distinct !DICompositeType(tag: DW_TAG_structure_type, name: "State", file: !5, line: 3, size: 64, elements: !7)
!7 = !{!8, !10}
!8 = !DIDerivedType(tag: DW_TAG_member, name: "data", scope: !6, file: !5, line: 3, baseType: !9, size: 32)
!9 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!10 = !DIDerivedType(tag: DW_TAG_member, name: "flag", scope: !6, file: !5, line: 3, baseType: !9, size: 32, offset: 32)
!11 = !{i32 7, !"Dwarf Version", i32 5}
!12 = !{i32 2, !"Debug Info Version", i32 3}
!13 = !{i32 1, !"wchar_size", i32 4}
!14 = !{i32 8, !"PIC Level", i32 2}
!15 = !{i32 7, !"PIE Level", i32 2}
!16 = !{i32 7, !"uwtable", i32 2}
!17 = !{i32 7, !"frame-pointer", i32 2}
!18 = !{!"Ubuntu clang version 18.1.3 (1ubuntu1)"}
!19 = distinct !DISubprogram(name: "writer", scope: !5, file: !5, line: 6, type: !20, scopeLine: 6, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!20 = !DISubroutineType(types: !21)
!21 = !{!22, !22}
!22 = !DIDerivedType(tag: DW_TAG_pointer_type, baseType: null, size: 64)
!23 = !{}
!24 = !DILocalVariable(name: "arg", arg: 1, scope: !19, file: !5, line: 6, type: !22)
!25 = !DILocation(line: 6, column: 20, scope: !19)
!26 = !DILocation(line: 7, column: 11, scope: !19)
!27 = !DILocation(line: 8, column: 16, scope: !19)
!28 = !DILocation(line: 9, column: 16, scope: !19)
!29 = !DILocation(line: 10, column: 5, scope: !19)
!30 = distinct !DISubprogram(name: "reader", scope: !5, file: !5, line: 13, type: !20, scopeLine: 13, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!31 = !DILocalVariable(name: "arg", arg: 1, scope: !30, file: !5, line: 13, type: !22)
!32 = !DILocation(line: 13, column: 20, scope: !30)
!33 = !DILocation(line: 14, column: 11, scope: !30)
!34 = !DILocalVariable(name: "seen_flag", scope: !30, file: !5, line: 15, type: !9)
!35 = !DILocation(line: 15, column: 9, scope: !30)
!36 = !DILocation(line: 15, column: 27, scope: !30)
!37 = !DILocalVariable(name: "seen_data", scope: !30, file: !5, line: 16, type: !9)
!38 = !DILocation(line: 16, column: 9, scope: !30)
!39 = !DILocation(line: 16, column: 27, scope: !30)
!40 = !DILocation(line: 17, column: 11, scope: !30)
!41 = !DILocation(line: 18, column: 11, scope: !30)
!42 = !DILocation(line: 19, column: 5, scope: !30)
!43 = distinct !DISubprogram(name: "main", scope: !5, file: !5, line: 22, type: !44, scopeLine: 22, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !23)
!44 = !DISubroutineType(types: !45)
!45 = !{!9}
!46 = !DILocalVariable(name: "first", scope: !43, file: !5, line: 23, type: !47)
!47 = !DIDerivedType(tag: DW_TAG_typedef, name: "pthread_t", file: !48, line: 27, baseType: !49)
!48 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/pthreadtypes.h", directory: "", checksumkind: CSK_MD5, checksum: "8a5acdbeec491eca11cf81cb1ef77ea7")
!49 = !DIBasicType(name: "unsigned long", size: 64, encoding: DW_ATE_unsigned)
!50 = !DILocation(line: 23, column: 15, scope: !43)
!51 = !DILocalVariable(name: "second", scope: !43, file: !5, line: 23, type: !47)
!52 = !DILocation(line: 23, column: 22, scope: !43)
!53 = !DILocation(line: 24, column: 5, scope: !43)
!54 = !DILocation(line: 25, column: 5, scope: !43)
!55 = !DILocation(line: 26, column: 18, scope: !43)
!56 = !DILocation(line: 26, column: 5, scope: !43)
!57 = !DILocation(line: 27, column: 18, scope: !43)
!58 = !DILocation(line: 27, column: 5, scope: !43)
!59 = !DILocation(line: 28, column: 5, scope: !43)
