import os
import sys
import re
import shutil
from datetime import datetime
import argparse
import toml
import yaml
from pathlib import Path
import anthropic
from typing import Optional, Tuple, Dict, List
import time

class ZolaToAstroConverter:
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

    @staticmethod
    def parse_date_from_filename(filename: str) -> Optional[str]:
        """Extract date from filename format YYYY-MM-DD-title.md"""
        match = re.match(r'(\d{4}-\d{2}-\d{2})-.*', filename)
        return match.group(1) if match else None

    @staticmethod
    def clean_filename(filename: str) -> str:
        """Remove date prefix from filename"""
        return re.sub(r'^\d{4}-\d{2}-\d{2}-', '', filename)

    @staticmethod
    def extract_zola_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
        """Extract Zola's TOML frontmatter between +++ markers"""
        try:
            # Find content between +++ markers
            pattern = r'\+\+\+(.*?)\+\+\+'
            match = re.search(pattern, content, re.DOTALL)
            
            if not match:
                return None, content
            
            frontmatter_raw = match.group(1).strip()
            remaining_content = content[match.end():].strip()
            
            # Parse TOML with proper error handling
            try:
                frontmatter_data = toml.loads(frontmatter_raw)
                return frontmatter_data, remaining_content
            except toml.TomlDecodeError as e:
                # Try to clean up the TOML before parsing
                cleaned_toml = frontmatter_raw.replace('\n\n', '\n').strip()
                try:
                    frontmatter_data = toml.loads(cleaned_toml)
                    return frontmatter_data, remaining_content
                except toml.TomlDecodeError:
                    print(f"Error parsing TOML even after cleanup: {e}")
                    print("Raw frontmatter content:")
                    print(frontmatter_raw)
                    return None, content
                
        except Exception as e:
            print(f"Error extracting frontmatter: {e}")
            return None, content

    def generate_description(self, content: str, title: str) -> str:
        """Generate a description using Anthropic's Claude API"""
        if not self.client:
            return ""
        
        # Remove markdown images and links for cleaner content
        cleaned_content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
        cleaned_content = re.sub(r'\[.*?\]\(.*?\)', '', cleaned_content)
        
        prompt = f"""Please write a concise 1-2 sentence description for a blog post titled "{title}". 
        Here's the content:
        {cleaned_content[:1500]}...
        
        Generate only the description, nothing else. Make it engaging but factual, 
        and keep it under 160 characters."""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Error generating description: {e}")
            return ""

    def generate_tags(self, content: str, title: str) -> List[str]:
        """Generate relevant tags using Anthropic's Claude API"""
        if not self.client:
            return []
        
        # Clean content for better tag generation
        cleaned_content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
        cleaned_content = re.sub(r'\[.*?\]\(.*?\)', '', cleaned_content)
        
        prompt = f"""Based on this blog post title and content, suggest 3-6 relevant tags.
        Title: "{title}"
        Content: {cleaned_content[:1500]}...
        
        Return only the tags as a comma-separated list, nothing else. Use lowercase words, 
        and include specific technologies or concepts mentioned."""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            tags = [tag.strip().lower() for tag in response.content[0].text.split(',')]
            return tags
        except Exception as e:
            print(f"Error generating tags: {e}")
            return []

    def create_astro_frontmatter(self, zola_data: Dict, pub_date: str, author: str, 
                               markdown_content: str) -> Dict:
        """Convert Zola frontmatter to Astro format with AI-generated content if needed"""
        # Start with basic required fields
        astro_data = {
            'title': zola_data.get('title', ''),
            'pubDate': pub_date,
            'author': author
        }
        
        # Handle description
        description = None
        if 'extra' in zola_data and 'lead' in zola_data['extra']:
            description = zola_data['extra']['lead']
        elif 'description' in zola_data:
            description = zola_data['description']
        
        if not description and self.client:
            description = self.generate_description(markdown_content, astro_data['title'])
            if description:
                print(f"Generated description: {description}")
        
        if description:
            astro_data['description'] = description

        # Handle tags
        tags = set()
        if 'taxonomies' in zola_data:
            if 'tags' in zola_data['taxonomies']:
                tags.update(zola_data['taxonomies']['tags'])
            if 'categories' in zola_data['taxonomies']:
                tags.update(zola_data['taxonomies']['categories'])
        
        if not tags and self.client:
            generated_tags = self.generate_tags(markdown_content, astro_data['title'])
            if generated_tags:
                tags.update(generated_tags)
                print(f"Generated tags: {', '.join(generated_tags)}")
        
        if tags:
            astro_data['tags'] = sorted(list(tags))
        
        return astro_data

    def convert_file(self, input_path: str, output_path: str, author: str) -> bool:
        """Convert a single Zola markdown file to Astro format"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract date from filename
            pub_date = self.parse_date_from_filename(os.path.basename(input_path))
            if not pub_date:
                print(f"Warning: Could not parse date from filename {input_path}")
                pub_date = datetime.now().strftime('%Y-%m-%d')
            
            # Parse Zola frontmatter
            zola_data, markdown_content = self.extract_zola_frontmatter(content)
            if not zola_data:
                print(f"Warning: Could not parse frontmatter in {input_path}")
                return False
            
            # Create Astro frontmatter with optional AI-generated content
            astro_data = self.create_astro_frontmatter(zola_data, pub_date, author, markdown_content)
            
            # Generate new content
            new_content = "---\n"
            new_content += yaml.dump(astro_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            new_content += "---\n\n"
            new_content += markdown_content
            
            # Write to new file
            output_filename = self.clean_filename(os.path.basename(input_path))
            output_file = os.path.join(output_path, output_filename)
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
            
        except Exception as e:
            print(f"Error converting file {input_path}: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Convert Zola blog posts to Astro format')
    parser.add_argument('input_dir', help='Input directory containing Zola markdown files')
    parser.add_argument('output_dir', help='Output directory for Astro markdown files')
    parser.add_argument('--author', default='Anonymous', help='Default author name for posts')
    parser.add_argument('--anthropic-key', help='Anthropic API key for generating descriptions and tags')
    parser.add_argument('--generate-missing', action='store_true', 
                       help='Generate missing descriptions and tags using Anthropic API')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making any changes')
    
    args = parser.parse_args()
    
    # Initialize converter
    converter = ZolaToAstroConverter(args.anthropic_key if args.generate_missing else None)
    
    if not args.dry_run:
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
    
    # Process all markdown files
    success_count = 0
    total_count = 0
    
    for root, _, files in os.walk(args.input_dir):
        for file in files:
            if file.endswith('.md'):
                total_count += 1
                input_path = os.path.join(root, file)
                
                # Maintain directory structure
                rel_path = os.path.relpath(root, args.input_dir)
                output_path = os.path.join(args.output_dir, rel_path)
                
                if args.dry_run:
                    print(f"Would convert: {file}")
                    continue
                
                if converter.convert_file(input_path, output_path, args.author):
                    success_count += 1
                    print(f"Converted: {file}")
                else:
                    print(f"Failed to convert: {file}")
                
                # Add small delay between API calls if using Anthropic
                if args.generate_missing:
                    time.sleep(1)
    
    print(f"\nConversion complete: {success_count}/{total_count} files converted successfully")

if __name__ == "__main__":
    main()