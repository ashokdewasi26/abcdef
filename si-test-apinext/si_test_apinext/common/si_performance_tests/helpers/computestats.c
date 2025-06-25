#include <fcntl.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

char *pname;
char *in_file;

#define DATA_COUNT (1024*1024)
u_int64_t data_items[DATA_COUNT];

int num_data_items = 0;

#define BUFSIZE 1024
char in_buf[BUFSIZE];

static int compare_long(const void *p1, const void *p2)
{
	u_int64_t val1 = *(u_int64_t *)p1;
	u_int64_t val2 = *(u_int64_t *)p2;

	if (val1 == val2)
		return 0;
	if (val1 < val2)
		return -1;

	return 1;
}

int main(int argc, char **argv)
{
	FILE *in_fp;
	FILE *report_fp;
	char default_file_name[30] = "perfo-app-launcher_report.csv";
	char file_name[200] = "";
	u_int64_t sum_x = 0;
	u_int64_t sum_sq_x = 0;
	u_int64_t min = 0;
	u_int64_t max = 0;
	u_int64_t mean;
	double std_dev;
	double std_dev_of_mean;
	int i;
	int one_sd = 0;
	int two_sd = 0;
	int three_sd = 0;
	double one_sd_low, one_sd_high;
	double two_sd_low, two_sd_high;
	double three_sd_low, three_sd_high;

	/*
	 * The following lines are commented because we will always
	 * read the information from stdin.
	 * > argv[0] - Executable name
	 * > argv[1] - Application name
	 * > argv[2] - Measure name
	 * > argv[3] - Path to store the file if you want to use a different location to store it
	 */

	// If argc = 3 it means that csv will be generated in the repository where the shell script is executed
	if (argc == 3 || argv[3] == NULL)
	{
		in_fp = stdin;
		strcpy(file_name, default_file_name);
	}
	// If argc = 4, it means that the user chose a folder to store the file
	else if (argc == 4)
	{
		in_fp = stdin;
		sprintf(file_name, "%s/%s", argv[3], default_file_name);
	}
	else
	{
		printf("Make sure you have the following arguments:\n");
		printf("\targv[0] - Executable name:\n");
		printf("\targv[1] - Application name\n");
		printf("\targv[2] - Measure name\n");
		printf("\targv[3] - Path to store the file if you want to use a different location to store it\n");

		return 0;
	}

	while (fgets(in_buf, BUFSIZE, in_fp))
	{
		if (num_data_items == DATA_COUNT)
		{
			fprintf(stderr, "DATA overflow, increase size of data_items array\n");
			exit(1);
		}

		sscanf(in_buf, "%ju", &data_items[num_data_items]);

#if 0
		printf("%lu\n", data_items[num_data_items++]);
#endif

		num_data_items++;
	}

	if (num_data_items == 0)
	{
		fprintf(stderr, "Empty input file ?\n");
		exit(1);
	}

#if 0
	printf("Total items %lu\n", num_data_items);
#endif

	for (i = 0 ; i < num_data_items ; i++)
	{
		/*
		 * In the first iteration of the data_items, fill in the minimum and maximum
		 * with this value to avoid that the minimum is always zero
		 */
		if (i == 0)
		{
			min = data_items[i];
			max = data_items[i];
		}

		sum_x += data_items[i];
		sum_sq_x += data_items[i] * data_items[i];

		if (data_items[i] < min)
			min = data_items[i];

		if (data_items[i] > max)
			max = data_items[i];
	}

	mean = sum_x / num_data_items;
	printf("\tMean %lu\n", mean);
	std_dev = sqrt((sum_sq_x / num_data_items) - (mean * mean));

	std_dev_of_mean = (std_dev * 100.0) / mean;

	// A non-zero value (true) if std_dev_of_mean is a NaN value; and zero (false) otherwise
	if (isnan(std_dev_of_mean) != 0)
	{
		std_dev_of_mean = 0;
		printf("\tStd Dev %.2f (%.2f%% of mean)\n", std_dev, std_dev_of_mean);
	}
	else
		printf("\tStd Dev %.2f (%.2f%% of mean)\n", std_dev, std_dev_of_mean);

	one_sd_low = mean - std_dev;
	one_sd_high = mean + std_dev;
	two_sd_low = mean - (2 * std_dev);
	two_sd_high = mean + (2 * std_dev);
	three_sd_low = mean - (3 * std_dev);
	three_sd_high = mean + (3 * std_dev);

	/* Check if the file already exists */
	if ( (access(file_name, F_OK)) != -1 )
	{
		/* The file exists */
		report_fp = fopen(file_name, "a+");
	}
	else
	{
		/* The file does not exist. Let's create the file! */
		report_fp = fopen(file_name, "w");
		fprintf(report_fp,"application,measure,mean(value),std_dev(value),std_dev_of_mean(per),min(value),max(value)\n");
	}

	fprintf(report_fp,"%s,%s,%lu,%.2f,%.2f,%lu,%lu\n", argv[1], argv[2], mean, std_dev, std_dev_of_mean, min, max);
	fclose(report_fp);

	for (i = 0 ; i < num_data_items ; i++)
	{
		if (data_items[i] >= one_sd_low && data_items[i] <= one_sd_high)
			one_sd++;
		if (data_items[i] >= two_sd_low && data_items[i] <= two_sd_high)
			two_sd++;
		if (data_items[i] >= three_sd_low && data_items[i] <= three_sd_high)
			three_sd++;
	}

	printf("\tWithin 1 SD %.2f%%\n", ((double)one_sd * 100) / num_data_items);
	printf("\tWithin 2 SD %.2f%%\n", ((double)two_sd * 100) / num_data_items);
	printf("\tWithin 3 SD %.2f%%\n", ((double)three_sd* 100) / num_data_items);
	printf("\tOutside 3 SD %.2f%%\n", ((double)(num_data_items - three_sd) * 100) / num_data_items);
	/* Sort the data to get percentiles */
	qsort(data_items, num_data_items, sizeof(u_int64_t), compare_long);
	printf("\t50th percentile %lu\n", data_items[num_data_items / 2]);
	printf("\t75th percentile %lu\n", data_items[(3 * num_data_items) / 4]);
	printf("\t90th percentile %lu\n", data_items[(9 * num_data_items) / 10]);
	printf("\t99th percentile %lu\n", data_items[(99 * num_data_items) / 100]);
}
