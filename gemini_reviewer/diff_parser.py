"""
Diff parser for the Gemini AI Code Reviewer.

This module handles parsing GitHub diffs into structured data models
and provides utilities for working with the parsed data.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Iterator
from unidiff import PatchSet, PatchedFile, Hunk

from .models import DiffFile, FileInfo, HunkInfo


logger = logging.getLogger(__name__)


class DiffParsingError(Exception):
    """Exception raised when diff parsing fails."""
    pass


class DiffParser:
    """Parser for GitHub diff content with comprehensive error handling."""
    
    def __init__(self):
        """Initialize the diff parser."""
        self._parsed_files_count = 0
        self._skipped_files_count = 0
        self._total_additions = 0
        self._total_deletions = 0
        
        logger.debug("Initialized diff parser")
    
    def parse_diff(self, diff_content: str) -> List[DiffFile]:
        """Parse diff content into structured DiffFile objects."""
        if not diff_content or not isinstance(diff_content, str):
            logger.warning("Empty or invalid diff content provided")
            return []
        
        logger.info(f"Parsing diff content (length: {len(diff_content)} characters)")
        
        try:
            # Try parsing with unidiff first (more robust)
            diff_files = self._parse_with_unidiff(diff_content)
            if diff_files:
                logger.info(f"Successfully parsed {len(diff_files)} files using unidiff")
                return diff_files
            else:
                logger.warning("Unidiff parsing returned 0 files, trying manual parsing")
        except Exception as e:
            logger.warning(f"Unidiff parsing failed: {str(e)}, trying manual parsing")
            logger.debug(f"Diff content preview: {diff_content[:500]}...")
        
        try:
            # Fallback to manual parsing
            diff_files = self._parse_manually(diff_content)
            logger.info(f"Successfully parsed {len(diff_files)} files using manual parser")
            return diff_files
        except Exception as e:
            logger.error(f"Manual diff parsing failed: {str(e)}")
            raise DiffParsingError(f"Failed to parse diff: {str(e)}")
    
    def _parse_with_unidiff(self, diff_content: str) -> List[DiffFile]:
        """Parse diff using the unidiff library."""
        try:
            patch_set = PatchSet(diff_content)
            logger.info(f"🔍 Unidiff PatchSet created with {len(patch_set)} files")
            
            # If no files found, show diff preview for debugging
            if len(patch_set) == 0:
                logger.warning(f"PatchSet is empty! Diff preview (first 1000 chars):")
                logger.warning(f"Diff content: {repr(diff_content[:1000])}")
                lines = diff_content.split('\n')
                logger.warning(f"Total lines: {len(lines)}")
                logger.warning(f"First 10 lines: {lines[:10]}")
                
            diff_files = []
            
            for i, patched_file in enumerate(patch_set):
                logger.debug(f"Processing patched file {i+1}: {patched_file.source_file} -> {patched_file.target_file}")
                diff_file = self._convert_patched_file(patched_file)
                if diff_file:
                    diff_files.append(diff_file)
                    self._parsed_files_count += 1
                    logger.debug(f"✅ Successfully converted file: {diff_file.file_info.path}")
                else:
                    self._skipped_files_count += 1
                    logger.debug(f"⚠️ Skipped file: {patched_file.source_file} -> {patched_file.target_file}")
            
            logger.info(f"Unidiff parsing completed: {len(diff_files)} files processed, {self._skipped_files_count} skipped")
            return diff_files
            
        except Exception as e:
            logger.warning(f"Unidiff parsing error: {str(e)}")
            logger.debug(f"Diff content preview: {diff_content[:1000]}...")
            raise
    
    def _convert_patched_file(self, patched_file: PatchedFile) -> Optional[DiffFile]:
        """Convert unidiff PatchedFile to our DiffFile model."""
        try:
            # Extract file information
            source_file = patched_file.source_file or ""
            target_file = patched_file.target_file or ""
            
            # Determine actual file path
            if target_file and target_file != "/dev/null":
                file_path = target_file[2:] if target_file.startswith("b/") else target_file
                old_path = source_file[2:] if source_file.startswith("a/") else source_file
            elif source_file and source_file != "/dev/null":
                file_path = source_file[2:] if source_file.startswith("a/") else source_file
                old_path = None
            else:
                logger.warning("Both source and target files are null")
                return None
            
            # Skip if path is invalid
            if not file_path or file_path in ["/dev/null", ""]:
                logger.debug(f"Skipping file with invalid path: {file_path}")
                return None
            
            # Create FileInfo
            file_info = FileInfo(
                path=file_path,
                old_path=old_path if old_path != file_path else None,
                is_new_file=patched_file.is_added_file,
                is_deleted_file=patched_file.is_removed_file,
                is_renamed_file=patched_file.is_renamed_file
            )
            
            # Skip binary files
            if file_info.is_binary:
                logger.debug(f"⚠️ Skipping binary file: {file_path}")
                return None
            
            # Convert hunks
            hunks = []
            for hunk in patched_file:
                hunk_info = self._convert_hunk(hunk)
                if hunk_info:
                    hunks.append(hunk_info)
            
            if not hunks:
                logger.debug(f"⚠️ No valid hunks found for file: {file_path}")
                return None
            
            diff_file = DiffFile(file_info=file_info, hunks=hunks)
            
            # Update statistics
            self._total_additions += diff_file.total_additions
            self._total_deletions += diff_file.total_deletions
            
            logger.debug(f"Converted file: {file_path} with {len(hunks)} hunks")
            return diff_file
            
        except Exception as e:
            logger.warning(f"Error converting patched file: {str(e)}")
            return None
    
    def _convert_hunk(self, hunk: Hunk) -> Optional[HunkInfo]:
        """Convert unidiff Hunk to our HunkInfo model."""
        try:
            # Extract hunk lines
            lines = []
            for line in hunk:
                line_content = str(line)
                lines.append(line_content)
            
            if not lines:
                logger.debug("Empty hunk found")
                return None
            
            # Create HunkInfo
            hunk_info = HunkInfo(
                source_start=hunk.source_start,
                source_length=hunk.source_length,
                target_start=hunk.target_start,
                target_length=hunk.target_length,
                content='\n'.join(lines),
                header=str(hunk).split('\n')[0],  # First line is the hunk header
                lines=lines
            )
            
            return hunk_info
            
        except Exception as e:
            logger.warning(f"Error converting hunk: {str(e)}")
            return None
    
    def _parse_manually(self, diff_content: str) -> List[DiffFile]:
        """Manual diff parsing as fallback."""
        diff_files = []
        current_file = None
        current_hunk = None
        
        lines = diff_content.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            try:
                if line.startswith('diff --git'):
                    # Save previous file if exists
                    if current_file and current_file.hunks:
                        diff_files.append(current_file)
                        self._parsed_files_count += 1
                    
                    # Start new file
                    current_file = self._parse_file_header(lines, i)
                    current_hunk = None
                    
                elif line.startswith('@@') and current_file:
                    # Start new hunk
                    current_hunk = self._parse_hunk_header(line)
                    if current_hunk:
                        current_file.hunks.append(current_hunk)
                
                elif current_hunk and (line.startswith(' ') or line.startswith('+') or line.startswith('-')):
                    # Add line to current hunk
                    current_hunk.lines.append(line)
                    current_hunk.content += line + '\n'
                
                i += 1
                
            except Exception as e:
                logger.warning(f"Error parsing line {i}: {str(e)}")
                i += 1
                continue
        
        # Don't forget the last file
        if current_file and current_file.hunks:
            diff_files.append(current_file)
            self._parsed_files_count += 1
        
        return diff_files
    
    def _parse_file_header(self, lines: List[str], start_index: int) -> DiffFile:
        """Parse file header information."""
        diff_line = lines[start_index]
        
        # Extract file paths from diff --git line
        match = re.match(r'diff --git a/(.+) b/(.+)', diff_line)
        if not match:
            raise DiffParsingError(f"Invalid diff header: {diff_line}")
        
        old_path, new_path = match.groups()
        
        # Determine file status by looking ahead
        is_new_file = False
        is_deleted_file = False
        is_renamed_file = old_path != new_path
        
        # Look for file mode changes or new/deleted indicators
        for i in range(start_index + 1, min(start_index + 10, len(lines))):
            if i >= len(lines):
                break
            
            line = lines[i]
            if line.startswith('new file mode'):
                is_new_file = True
            elif line.startswith('deleted file mode'):
                is_deleted_file = True
            elif line.startswith('@@'):
                break
        
        # Create FileInfo
        file_info = FileInfo(
            path=new_path,
            old_path=old_path if is_renamed_file else None,
            is_new_file=is_new_file,
            is_deleted_file=is_deleted_file,
            is_renamed_file=is_renamed_file
        )
        
        return DiffFile(file_info=file_info, hunks=[])
    
    def _parse_hunk_header(self, header_line: str) -> Optional[HunkInfo]:
        """Parse hunk header information."""
        # Parse hunk header: @@ -start,length +start,length @@ context
        match = re.match(r'@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', header_line)
        if not match:
            logger.warning(f"Invalid hunk header: {header_line}")
            return None
        
        source_start, source_length, target_start, target_length = match.groups()
        
        return HunkInfo(
            source_start=int(source_start),
            source_length=int(source_length) if source_length else 1,
            target_start=int(target_start),
            target_length=int(target_length) if target_length else 1,
            content="",
            header=header_line,
            lines=[]
        )
    
    def filter_files(
        self,
        diff_files: List[DiffFile],
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_files: Optional[int] = None,
        min_changes: int = 1
    ) -> List[DiffFile]:
        """Filter diff files based on various criteria."""
        if not diff_files:
            return []
        
        filtered_files = []
        
        for diff_file in diff_files:
            file_path = diff_file.file_info.path
            
            # Check include patterns
            if include_patterns:
                if not any(self._matches_pattern(file_path, pattern) for pattern in include_patterns):
                    logger.debug(f"File {file_path} doesn't match include patterns")
                    continue
            
            # Check exclude patterns
            if exclude_patterns:
                if any(self._matches_pattern(file_path, pattern) for pattern in exclude_patterns):
                    logger.debug(f"File {file_path} matches exclude pattern")
                    continue
            
            # Check minimum changes
            total_changes = diff_file.total_additions + diff_file.total_deletions
            if total_changes < min_changes:
                logger.debug(f"File {file_path} has too few changes ({total_changes})")
                continue
            
            # Check if binary file
            if diff_file.file_info.is_binary:
                logger.debug(f"Skipping binary file: {file_path}")
                continue
            
            filtered_files.append(diff_file)
            
            # Check max files limit
            if max_files and len(filtered_files) >= max_files:
                logger.info(f"Reached maximum files limit ({max_files})")
                break
        
        logger.info(f"Filtered {len(diff_files)} files down to {len(filtered_files)}")
        return filtered_files
    
    def filter_large_hunks(
        self,
        diff_files: List[DiffFile],
        max_lines_per_hunk: int = 500,
        max_hunks_per_file: int = 20
    ) -> List[DiffFile]:
        """Filter out or truncate large hunks to manage token usage."""
        filtered_files = []
        
        for diff_file in diff_files:
            # Filter hunks
            filtered_hunks = []
            
            for hunk in diff_file.hunks[:max_hunks_per_file]:  # Limit hunks per file
                if len(hunk.lines) > max_lines_per_hunk:
                    logger.debug(f"Truncating large hunk in {diff_file.file_info.path} "
                               f"({len(hunk.lines)} -> {max_lines_per_hunk} lines)")
                    
                    # Truncate hunk
                    truncated_lines = hunk.lines[:max_lines_per_hunk]
                    truncated_content = '\n'.join(truncated_lines)
                    
                    truncated_hunk = HunkInfo(
                        source_start=hunk.source_start,
                        source_length=min(hunk.source_length, max_lines_per_hunk),
                        target_start=hunk.target_start,
                        target_length=min(hunk.target_length, max_lines_per_hunk),
                        content=truncated_content + '\n...[truncated]',
                        header=hunk.header,
                        lines=truncated_lines
                    )
                    filtered_hunks.append(truncated_hunk)
                else:
                    filtered_hunks.append(hunk)
            
            if filtered_hunks:
                filtered_file = DiffFile(
                    file_info=diff_file.file_info,
                    hunks=filtered_hunks
                )
                filtered_files.append(filtered_file)
        
        return filtered_files
    
    @staticmethod
    def _matches_pattern(file_path: str, pattern: str) -> bool:
        """Check if file path matches a pattern using glob matching."""
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)
    
    def get_parsing_statistics(self) -> Dict[str, Any]:
        """Get parsing statistics."""
        return {
            'parsed_files': self._parsed_files_count,
            'skipped_files': self._skipped_files_count,
            'total_additions': self._total_additions,
            'total_deletions': self._total_deletions,
            'total_changes': self._total_additions + self._total_deletions
        }
    
    def reset_statistics(self):
        """Reset parsing statistics."""
        self._parsed_files_count = 0
        self._skipped_files_count = 0
        self._total_additions = 0
        self._total_deletions = 0
    
    @staticmethod
    def get_file_language(file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        if not file_path or '.' not in file_path:
            return None
        
        extension = file_path.split('.')[-1].lower()
        language_mapping = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'jsx': 'React', 'tsx': 'TypeScript React',
            'java': 'Java', 'cpp': 'C++', 'c': 'C', 'cs': 'C#',
            'go': 'Go', 'rs': 'Rust', 'php': 'PHP', 'rb': 'Ruby',
            'swift': 'Swift', 'kt': 'Kotlin', 'scala': 'Scala',
            'html': 'HTML', 'css': 'CSS', 'scss': 'SCSS',
            'json': 'JSON', 'yaml': 'YAML', 'yml': 'YAML',
            'sql': 'SQL', 'sh': 'Shell', 'bash': 'Bash'
        }
        return language_mapping.get(extension)
    
    @staticmethod
    def analyze_diff_complexity(diff_files: List[DiffFile]) -> Dict[str, Any]:
        """Analyze the complexity of the diff for processing decisions."""
        if not diff_files:
            return {'complexity': 'none', 'total_files': 0}
        
        total_files = len(diff_files)
        total_hunks = sum(len(df.hunks) for df in diff_files)
        total_lines = sum(len(hunk.lines) for df in diff_files for hunk in df.hunks)
        
        # Categorize complexity
        if total_files > 20 or total_lines > 2000:
            complexity = 'high'
        elif total_files > 10 or total_lines > 1000:
            complexity = 'medium'
        else:
            complexity = 'low'
        
        return {
            'complexity': complexity,
            'total_files': total_files,
            'total_hunks': total_hunks,
            'total_lines': total_lines,
            'avg_hunks_per_file': total_hunks / total_files if total_files > 0 else 0,
            'avg_lines_per_file': total_lines / total_files if total_files > 0 else 0
        }
